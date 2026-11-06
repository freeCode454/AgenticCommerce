"""PostgreSQL-backed worker with session locks and conservative crash recovery.

Pending jobs survive process restarts. Running jobs without their session lock are
interrupted, never automatically replayed: a provider may already have billed.
"""

import asyncio
import logging
from contextlib import suppress
from typing import Any

from sqlalchemy import case, select, text

from app.clients.postgres import AsyncSessionLocal, engine
from app.conf.config import settings
from app.core.task_execution import ExecutionContext, active_execution
from app.models.base import utc_now
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_execution import TaskExecution
from app.models.tenant import Tenant
from app.services.provider_runtime import provider_scope
from app.services.task_queue import advisory_key, refresh_batch

logger = logging.getLogger("task_worker")
INTERRUPTED = "执行因服务停止或数据库连接中断而终止。模型请求可能已经产生费用；系统未自动重跑，请核对已有产物后手动重新生成。"


async def execute_workflow(
    task_id: str, tenant_id: str, sku_id: str, config: dict
) -> dict[str, Any]:
    from app.agent.graph import app_workflow

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
    async with provider_scope(tenant_id):
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
                select(TaskExecution.id)
                .where(
                    TaskExecution.tenant_id == "__schema_check__",
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
                            .where(
                                Task.tenant_id == tenant_id,
                                Task.is_deleted == 0,
                                Task.status.in_(("pending", "running", "retrying")),
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
            if execution is None or execution.status != "pending":
                # We hold the session lock, so no healthy worker owns this task.
                task.status, task.error_message = "failed", INTERRUPTED
                if execution and execution.status == "running":
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
            execution.status, execution.started_at = "running", utc_now()
            task.status, task.current_node = "running", "orchestrator"
            await refresh_batch(session, tenant_id, task.batch_id)
            await session.commit()
            return {
                "task_id": task_id,
                "tenant_id": tenant_id,
                "sku_id": task.sku_id,
                "config": task.config or {},
                "execution_id": execution.id,
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
            execution.status, execution.finished_at, execution.error_message = (
                status,
                utc_now(),
                message,
            )
            task.status = "completed" if status == "completed" else "failed"
            task.error_message = message
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
