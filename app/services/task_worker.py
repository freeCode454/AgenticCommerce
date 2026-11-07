"""PostgreSQL-backed worker with session locks and conservative crash recovery.

Pending jobs survive process restarts. Running jobs without their session lock are
interrupted, never automatically replayed: a provider may already have billed.
"""

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, case, func, or_, select, text

from app.api.task_config import TaskConfig
from app.clients.postgres import AsyncSessionLocal, engine
from app.clients.wan_video import RemoteVideoPending, SubmissionUnknownError
from app.conf.config import settings
from app.core.task_execution import ExecutionContext, active_execution
from app.models.base import utc_now
from app.models.provider_job import ProviderJob
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_execution import TaskExecution
from app.models.tenant import Tenant
from app.services.provider_runtime import provider_scope
from app.services.task_queue import advisory_key, refresh_batch
from app.services.workflow_checkpoint import (
    mark_unknown_submission,
    recoverable_state,
    save_provider_snapshot,
)

logger = logging.getLogger("task_worker")
INTERRUPTED = "执行因服务停止或数据库连接中断而终止。模型请求可能已经产生费用；系统未自动重跑，请核对已有产物后手动重新生成。"


async def execute_workflow(
    task_id: str,
    tenant_id: str,
    sku_id: str,
    config: dict,
    resume_state: dict | None = None,
) -> dict[str, Any]:
    from app.agent.graph import app_workflow

    if resume_state is not None:
        if (
            resume_state.get("task_id") != task_id
            or resume_state.get("tenant_id") != tenant_id
        ):
            raise ValueError("Recovery state does not belong to this task")
        return await app_workflow.ainvoke(resume_state)

    config = TaskConfig.model_validate(config).model_dump()
    async with AsyncSessionLocal() as session:
        sku = (
            await session.execute(
                select(Sku).where(
                    Sku.id == sku_id,
                    Sku.tenant_id == tenant_id,
                    Sku.is_deleted == 0,
                )
            )
        ).scalar_one_or_none()
        if sku is None:
            raise ValueError("SKU not found for tenant")
        sku_data = {
            key: getattr(sku, key)
            for key in (
                "id",
                "code",
                "name",
                "category",
                "specs",
                "description",
                "images",
            )
        }
    async with provider_scope(tenant_id) as snapshot:
        await save_provider_snapshot(snapshot)
        return await app_workflow.ainvoke(
            {
                "task_id": task_id,
                "tenant_id": tenant_id,
                "sku_id": sku_id,
                "sku_data": sku_data,
                "config": config,
                "retry_count": 0,
                "max_retries": config.get("max_retries", 2),
                "completed_steps": [],
            }
        )


class TaskWorker:
    def __init__(
        self,
        *,
        database_engine=engine,
        session_factory=AsyncSessionLocal,
        runner=execute_workflow,
        concurrency: int | None = None,
    ):
        self.engine, self.sessions, self.runner = (
            database_engine,
            session_factory,
            runner,
        )
        self.concurrency = concurrency or settings.TASK_WORKER_CONCURRENCY
        self.jobs: dict[tuple[str, str], asyncio.Task] = {}
        self.loop: asyncio.Task | None = None
        self.tenant_cursor = 0
        self.scan_cursors: dict[str, int] = {}

    async def start(self) -> None:
        # Fail startup clearly when the database has not been migrated.
        async with self.sessions() as session:
            await session.execute(
                select(TaskExecution.state_snapshot, TaskExecution.next_poll_at)
                .where(
                    TaskExecution.tenant_id == "__schema_check__",
                )
                .limit(1)
            )
            await session.execute(
                select(ProviderJob.id)
                .where(
                    ProviderJob.tenant_id == "__schema_check__",
                )
                .limit(1)
            )
        self.loop = asyncio.create_task(self.serve(), name="durable-task-worker")

    async def stop(self) -> None:
        if self.loop:
            self.loop.cancel()
            await asyncio.gather(self.loop, return_exceptions=True)
        for job in self.jobs.values():
            job.cancel()
        await asyncio.gather(*self.jobs.values(), return_exceptions=True)
        self.jobs.clear()

    async def serve(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as error:  # noqa: BLE001 -- Isolate jobs; never log provider response bodies.
                logger.error("Queue poll failed (%s)", type(error).__name__)
            await asyncio.sleep(settings.TASK_WORKER_POLL_SECONDS)

    async def tick(self) -> None:
        for key, job in list(self.jobs.items()):
            if job.done():
                if not job.cancelled() and job.exception():
                    logger.error(
                        "Queue job failed (%s)", type(job.exception()).__name__
                    )
                del self.jobs[key]
        if len(self.jobs) >= self.concurrency:
            return
        async with self.sessions() as session:
            # Global scheduler discovers only tenant IDs in the global tenant table.
            # Every business-table query below is explicitly scoped to one tenant.
            tenants = (
                (
                    await session.execute(
                        select(Tenant.id)
                        .where(
                            Tenant.is_deleted == 0,
                        )
                        .order_by(Tenant.id)
                    )
                )
                .scalars()
                .all()
            )
            if tenants:
                offset = self.tenant_cursor % len(tenants)
                tenants = tenants[offset:] + tenants[:offset]
                self.tenant_cursor += 1
            for tenant_id in tenants:
                ids = (
                    (
                        await session.execute(
                            select(Task.id)
                            .outerjoin(
                                TaskExecution,
                                and_(
                                    TaskExecution.id == Task.execution_id,
                                    TaskExecution.tenant_id == tenant_id,
                                    TaskExecution.task_id == Task.id,
                                ),
                            )
                            .where(
                                Task.tenant_id == tenant_id,
                                Task.is_deleted == 0,
                                Task.status.in_(("pending", "running", "retrying")),
                                or_(
                                    TaskExecution.next_poll_at.is_(None),
                                    TaskExecution.next_poll_at <= func.now(),
                                ),
                            )
                            .order_by(
                                case((Task.status == "pending", 0), else_=1),
                                Task.create_time,
                                Task.id,
                            )
                            .limit(100)
                        )
                    )
                    .scalars()
                    .all()
                )
                if ids:
                    offset = self.scan_cursors.get(tenant_id, 0) % len(ids)
                    ids = ids[offset:] + ids[:offset]
                    self.scan_cursors[tenant_id] = offset + self.concurrency
                for task_id in ids:
                    key = (tenant_id, task_id)
                    if key in self.jobs:
                        continue
                    self.jobs[key] = asyncio.create_task(
                        self.run_one(tenant_id, task_id)
                    )
                    if len(self.jobs) >= self.concurrency:
                        return

    async def claim(self, tenant_id: str, task_id: str) -> dict | None:
        async with self.sessions() as session:
            task = (
                await session.execute(
                    select(Task)
                    .where(
                        Task.id == task_id,
                        Task.tenant_id == tenant_id,
                        Task.is_deleted == 0,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if task is None or task.status not in {"pending", "running", "retrying"}:
                return None
            execution = (
                await session.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.id == task.execution_id,
                        TaskExecution.task_id == task_id,
                        TaskExecution.tenant_id == tenant_id,
                        TaskExecution.is_deleted == 0,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            tenant = (
                await session.execute(
                    select(Tenant).where(
                        Tenant.id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if (
                execution
                and execution.next_poll_at
                and execution.next_poll_at > utc_now()
            ):
                return None
            has_started = execution is not None and bool(
                execution.state_snapshot or execution.started_at
            )
            resume = (
                await recoverable_state(session, task, execution)
                if has_started
                else None
            )
            if (
                execution is None
                or execution.status not in {"pending", "running"}
                or (execution.status == "running" and resume is None)
                or (has_started and resume is None)
            ):
                # We hold the session lock, so no healthy worker owns this task.
                task.status, task.error_message = "failed", INTERRUPTED
                if execution:
                    await mark_unknown_submission(
                        session, tenant_id, task_id, execution.id
                    )
                if execution and execution.status in {"pending", "running"}:
                    execution.status, execution.error_message = (
                        "interrupted",
                        INTERRUPTED,
                    )
                    execution.finished_at = utc_now()
                await refresh_batch(session, tenant_id, task.batch_id)
                await session.commit()
                await self.broadcast(tenant_id, task_id)
                return None
            if tenant is None or tenant.status != "active" or tenant.is_deleted:
                execution.status = "failed"
                execution.finished_at = utc_now()
                execution.error_message = task.error_message = (
                    "租户已停用，未发起模型请求。"
                )
                task.status = "failed"
                await refresh_batch(session, tenant_id, task.batch_id)
                await session.commit()
                await self.broadcast(tenant_id, task_id)
                return None
            execution.status = "running"
            execution.started_at = execution.started_at or utc_now()
            execution.next_poll_at = None
            task.status, task.current_node = "running", "orchestrator"
            await refresh_batch(session, tenant_id, task.batch_id)
            await session.commit()
            return {
                "task_id": task_id,
                "tenant_id": tenant_id,
                "sku_id": task.sku_id,
                "config": task.config or {},
                "execution_id": execution.id,
                **({"resume_state": resume} if resume is not None else {}),
            }

    async def finish(
        self, context: ExecutionContext, status: str, message: str | None = None
    ) -> None:
        async with self.sessions() as session:
            task = (
                await session.execute(
                    select(Task)
                    .where(
                        Task.id == context.task_id,
                        Task.tenant_id == context.tenant_id,
                        Task.execution_id == context.execution_id,
                        Task.is_deleted == 0,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            execution = (
                await session.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.id == context.execution_id,
                        TaskExecution.task_id == context.task_id,
                        TaskExecution.tenant_id == context.tenant_id,
                        TaskExecution.status == "running",
                        TaskExecution.is_deleted == 0,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if task is None or execution is None:
                return
            recover = (
                await recoverable_state(session, task, execution)
                if status in {"waiting", "interrupted"}
                else None
            )
            if recover is not None:
                job = (
                    await session.execute(
                        select(ProviderJob).where(
                            ProviderJob.tenant_id == context.tenant_id,
                            ProviderJob.task_id == context.task_id,
                            ProviderJob.execution_id == context.execution_id,
                            ProviderJob.round == recover.get("retry_count", 0),
                            ProviderJob.is_deleted == 0,
                        )
                    )
                ).scalar_one()
                delay = (
                    min(
                        300,
                        settings.VIDEO_POLL_SECONDS * 2 ** min(job.query_failures, 5),
                    )
                    if status == "waiting"
                    else 0
                )
                execution.status, execution.finished_at, execution.error_message = (
                    "pending",
                    None,
                    None,
                )
                execution.next_poll_at = utc_now() + timedelta(seconds=delay)
                task.status, task.error_message = "running", None
            else:
                if status == "waiting":
                    status, message = (
                        "interrupted",
                        "恢复记录不完整，未自动重新提交视频任务，请核对厂商记录。",
                    )
                execution.status, execution.finished_at, execution.error_message = (
                    status,
                    utc_now(),
                    message,
                )
                task.status = "completed" if status == "completed" else "failed"
                task.error_message = message
                execution.next_poll_at = None
                if status == "interrupted":
                    await mark_unknown_submission(
                        session,
                        context.tenant_id,
                        context.task_id,
                        context.execution_id,
                    )
            await refresh_batch(session, context.tenant_id, task.batch_id)
            await session.commit()
        await self.broadcast(context.tenant_id, context.task_id)

    @staticmethod
    async def broadcast(tenant_id: str, task_id: str) -> None:
        from app.api.v1.ws import ws_manager

        try:
            await ws_manager.broadcast(
                {"type": "task_update", "task_id": task_id}, tenant_id=tenant_id
            )
        except Exception as error:  # noqa: BLE001 -- Isolate jobs; never log provider response bodies.
            # Database is the source of truth; an unavailable socket cannot roll it back.
            logger.warning("Task notification failed (%s)", type(error).__name__)

    async def heartbeat(self, connection) -> None:
        while True:
            await asyncio.sleep(settings.TASK_WORKER_HEARTBEAT_SECONDS)
            await asyncio.wait_for(connection.execute(text("SELECT 1")), timeout=3)
            await connection.commit()

    async def run_one(self, tenant_id: str, task_id: str) -> bool:
        key = advisory_key("task", tenant_id, task_id)
        async with self.engine.connect() as connection:
            try:
                locked = await connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                )
                await connection.commit()
            except BaseException:
                await connection.invalidate()
                raise
            if not locked:
                return False
            context = token = invoke = monitor = None
            try:
                claimed = await self.claim(tenant_id, task_id)
                if claimed is None:
                    return False
                context = ExecutionContext(
                    tenant_id, task_id, claimed.pop("execution_id")
                )
                token = active_execution.set(context)
                await self.broadcast(tenant_id, task_id)
                invoke = asyncio.create_task(self.runner(**claimed))
                monitor = asyncio.create_task(self.heartbeat(connection))
                done, _ = await asyncio.wait(
                    (invoke, monitor), return_when=asyncio.FIRST_COMPLETED
                )
                if monitor in done:
                    invoke.cancel()
                    await asyncio.gather(invoke, return_exceptions=True)
                    await self.finish(context, "interrupted", INTERRUPTED)
                    return False
                result = await invoke
                passed = result.get("is_passed") is True
                await self.finish(
                    context,
                    "completed" if passed else "failed",
                    None
                    if passed
                    else "审核未通过或生成结果不完整，请检查本次执行记录。",
                )
                return True
            except RemoteVideoPending:
                if context:
                    await self.finish(context, "waiting")
                return False
            except SubmissionUnknownError as error:
                if context:
                    await self.finish(context, "interrupted", str(error))
                return False
            except asyncio.CancelledError:
                if invoke:
                    invoke.cancel()
                    await asyncio.gather(invoke, return_exceptions=True)
                if context:
                    with suppress(Exception):
                        await self.finish(context, "interrupted", INTERRUPTED)
                raise
            except Exception as error:  # noqa: BLE001 -- Isolate jobs; never log provider response bodies.
                logger.error(
                    "Workflow failed: task_id=%s, error=%s",
                    task_id,
                    type(error).__name__,
                )
                if context:
                    await self.finish(
                        context,
                        "failed",
                        f"工作流执行失败 ({type(error).__name__})，请检查本次节点记录和模型配置。",
                    )
                return False
            finally:
                for pending in (invoke, monitor):
                    if pending:
                        pending.cancel()
                await asyncio.gather(
                    *(job for job in (invoke, monitor) if job), return_exceptions=True
                )
                if token is not None:
                    active_execution.reset(token)
                try:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                    )
                    await connection.commit()
                except Exception:  # noqa: BLE001 -- Discard a connection whose lock cannot be released.
                    await connection.invalidate()
