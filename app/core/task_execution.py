"""Fence writes and new model requests to the current durable attempt."""

from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.task_execution import TaskExecution


class ExecutionSupersededError(RuntimeError):
    """The attempt no longer owns this task; fail closed."""


@dataclass(frozen=True)
class ExecutionContext:
    tenant_id: str
    task_id: str
    execution_id: str


active_execution: ContextVar[ExecutionContext | None] = ContextVar(
    "active_execution", default=None
)


async def fence_execution(
    session: AsyncSession,
    *,
    tenant_id: str | None = None,
    task_id: str | None = None,
) -> str | None:
    context = active_execution.get()
    if context is None:
        return None
    if (tenant_id is not None and context.tenant_id != tenant_id) or (
        task_id is not None and context.task_id != task_id
    ):
        raise ExecutionSupersededError("任务执行上下文不匹配")
    # Always lock Task before TaskExecution, matching enqueue/finalize lock order.
    task = (
        await session.execute(
            select(Task.id)
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
            select(TaskExecution.id)
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
        raise ExecutionSupersededError("任务已中断或被新的执行替代")
    return context.execution_id


async def guard_model_request() -> None:
    if active_execution.get() is not None:
        from app.clients.postgres import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await fence_execution(session)
