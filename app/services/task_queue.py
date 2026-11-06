"""Transactional enqueue, request deduplication and task/batch reconciliation."""

import hashlib
import json

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import generate_uuid32
from app.models.batch import Batch
from app.models.task import Task
from app.models.task_execution import TaskExecution


class TaskConflictError(ValueError):
    """A request conflicts with an existing execution or idempotency key."""


def advisory_key(*parts: str) -> int:
    return int.from_bytes(
        hashlib.sha256(json.dumps(parts).encode()).digest()[:8], "big", signed=True
    )


def request_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


async def deduplicate(
    session: AsyncSession,
    model: type[Task] | type[Batch],
    tenant_id: str,
    key: str | None,
    payload: dict,
) -> tuple[Task | Batch | None, str]:
    fingerprint = request_hash(payload)
    if key is None:
        return None, fingerprint
    if not key.strip() or len(key) > 128:
        raise TaskConflictError("Idempotency-Key 必须为 1–128 个字符")
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {
            "key": advisory_key("request", model.__tablename__, tenant_id, key),
        },
    )
    existing = (
        await session.execute(
            select(model).where(
                model.tenant_id == tenant_id,
                model.request_key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and (
        existing.request_hash != fingerprint or existing.is_deleted
    ):
        raise TaskConflictError("此请求标识已用于其他内容，请刷新后重新提交")
    return existing, fingerprint


def enqueue(
    session: AsyncSession,
    task: Task,
    user_id: str | None = None,
    request_key: str | None = None,
) -> TaskExecution:
    execution = TaskExecution(
        id=generate_uuid32(),
        tenant_id=task.tenant_id,
        task_id=task.id,
        status="pending",
        created_by=user_id,
        request_key=request_key,
    )
    task.execution_id = execution.id
    task.status = "pending"
    task.current_node = None
    task.retry_count = 0
    task.error_message = None
    session.add(execution)
    return execution


async def refresh_batch(
    session: AsyncSession, tenant_id: str, batch_id: str | None
) -> None:
    if not batch_id:
        return
    batch = (
        await session.execute(
            select(Batch)
            .where(
                Batch.id == batch_id,
                Batch.tenant_id == tenant_id,
                Batch.is_deleted == 0,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if batch is None:
        return
    await session.flush()
    counts = dict(
        (
            await session.execute(
                select(Task.status, func.count())
                .where(
                    Task.batch_id == batch_id,
                    Task.tenant_id == tenant_id,
                    Task.is_deleted == 0,
                )
                .group_by(Task.status)
            )
        ).all()
    )
    batch.total_count = sum(counts.values())
    batch.completed_count = counts.get("completed", 0)
    batch.failed_count = counts.get("failed", 0)
    if counts.get("running", 0) or counts.get("retrying", 0):
        batch.status = "running"
    elif counts.get("pending", 0):
        batch.status = "pending"
    elif counts.get("review_required", 0):
        batch.status = "review_required"
    elif batch.failed_count:
        batch.status = "failed"
    else:
        batch.status = "completed"
