"""Persist node boundaries; resume only known remote-video queries or unstarted review."""

import json
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select

from app.clients.postgres import AsyncSessionLocal
from app.conf.config import settings
from app.core.provider_context import (
    ProviderBinding,
    ProviderSnapshot,
    active_providers,
)
from app.core.provider_keys import (
    ProviderConfigurationError,
    decrypt_api_key,
    encrypt_api_key,
)
from app.core.task_execution import active_execution, fence_execution
from app.models.provider_job import ProviderJob
from app.models.task import Task
from app.models.task_execution import TaskExecution

NEXT = {
    "orchestrator": "requirement_analyzer",
    "requirement_analyzer": "creative_planner",
    "creative_planner": "visual_designer",
    "visual_designer": "image_generator",
    "image_generator": "video_generator",
    "video_generator": "quality_reviewer",
}


async def save_provider_snapshot(snapshot: ProviderSnapshot) -> None:
    context = active_execution.get()
    if context is None:
        return
    defaults = {
        "llm": ("qwen-plus", settings.DASHSCOPE_API_KEY),
        "image": (
            "qwen-image-3.0-pro",
            settings.WANX_API_KEY or settings.DASHSCOPE_API_KEY,
        ),
        "video": ("wan3.0-video", settings.DASHSCOPE_API_KEY),
    }
    stored = {}
    for kind, (model, key) in defaults.items():
        binding = snapshot.get(kind) or ProviderBinding("", model, key)
        stored[kind] = {
            "provider_id": binding.provider_id,
            "model": binding.model,
            "embedding_model": binding.embedding_model,
            "api_base": (binding.api_base or settings.DASHSCOPE_VIDEO_API_BASE)
            if kind == "video"
            else None,
            "api_key_enc": encrypt_api_key(
                binding.api_key,
                context.tenant_id,
                context.execution_id + ":" + kind,
                settings.PROVIDER_ENCRYPTION_KEY,
            ),
        }
    async with AsyncSessionLocal() as session:
        await fence_execution(session)
        execution = (
            await session.execute(
                select(TaskExecution).where(
                    TaskExecution.id == context.execution_id,
                    TaskExecution.tenant_id == context.tenant_id,
                    TaskExecution.task_id == context.task_id,
                    TaskExecution.is_deleted == 0,
                )
            )
        ).scalar_one()
        execution.provider_snapshot_enc = stored
        await session.commit()


@asynccontextmanager
async def frozen_provider_scope(kind: str):
    context = active_execution.get()
    if context is None:
        raise ProviderConfigurationError("恢复模型配置缺少执行身份。")
    async with AsyncSessionLocal() as session:
        await fence_execution(session)
        execution = (
            await session.execute(
                select(TaskExecution).where(
                    TaskExecution.id == context.execution_id,
                    TaskExecution.tenant_id == context.tenant_id,
                    TaskExecution.task_id == context.task_id,
                    TaskExecution.is_deleted == 0,
                )
            )
        ).scalar_one()
        stored = (execution.provider_snapshot_enc or {}).get(kind)
    if not isinstance(stored, dict):
        raise ProviderConfigurationError(
            "原始执行缺少模型配置快照，未调用其他模型替代。"
        )
    binding = ProviderBinding(
        stored["provider_id"],
        stored["model"],
        decrypt_api_key(
            stored["api_key_enc"],
            context.tenant_id,
            context.execution_id + ":" + kind,
            settings.PROVIDER_ENCRYPTION_KEY,
        ),
        stored["embedding_model"],
        api_base=stored.get("api_base"),
    )
    token = active_providers.set(
        ProviderSnapshot(context.tenant_id, ((kind, binding),))
    )
    try:
        yield
    finally:
        active_providers.reset(token)


async def checkpoint_node(name: str, state: dict, result: dict | None = None) -> None:
    context = active_execution.get()
    if context is None:
        return
    snapshot = dict(state)
    snapshot.pop("resume_node", None)
    if result is not None:
        snapshot.update(result)
        snapshot["completed_steps"] = list(state.get("completed_steps", [])) + list(
            result.get("completed_steps", [])
        )
    # JSON round-trip rejects accidental runtime objects; provider credentials never enter AgentState.
    snapshot = json.loads(json.dumps(snapshot, ensure_ascii=False, allow_nan=False))
    async with AsyncSessionLocal() as session:
        await fence_execution(
            session, tenant_id=state["tenant_id"], task_id=state["task_id"]
        )
        execution = (
            await session.execute(
                select(TaskExecution).where(
                    TaskExecution.id == context.execution_id,
                    TaskExecution.tenant_id == context.tenant_id,
                    TaskExecution.task_id == context.task_id,
                    TaskExecution.is_deleted == 0,
                )
            )
        ).scalar_one()
        execution.state_snapshot = snapshot
        execution.in_flight_node = name if result is None else None
        execution.next_node = (
            name
            if result is None
            else (
                "creative_planner"
                if name == "quality_reviewer" and snapshot.get("should_retry")
                else NEXT.get(name)
            )
        )
        execution.next_poll_at = None
        await session.commit()


async def recoverable_state(
    session, task: Task, execution: TaskExecution
) -> dict[str, Any] | None:
    state = execution.state_snapshot
    if (
        not isinstance(state, dict)
        or state.get("task_id") != task.id
        or state.get("tenant_id") != task.tenant_id
        or state.get("sku_id") != task.sku_id
        or not isinstance(state.get("config"), dict)
        or not isinstance(state.get("retry_count", 0), int)
    ):
        return None
    phase = execution.in_flight_node or execution.next_node
    if phase not in ("video_generator", "quality_reviewer"):
        return None
    if phase == "quality_reviewer" and execution.in_flight_node is not None:
        return None
    job = (
        await session.execute(
            select(ProviderJob).where(
                ProviderJob.tenant_id == task.tenant_id,
                ProviderJob.task_id == task.id,
                ProviderJob.execution_id == execution.id,
                ProviderJob.round == state.get("retry_count", 0),
                ProviderJob.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if (
        job is None
        or not job.remote_id
        or job.status in ("submitting", "submission_unknown")
    ):
        return None
    if phase == "quality_reviewer" and (
        job.status != "succeeded" or not state.get("generated_video")
    ):
        return None
    return {**state, "resume_node": phase}


async def mark_unknown_submission(
    session, tenant_id: str, task_id: str, execution_id: str
) -> None:
    jobs = (
        (
            await session.execute(
                select(ProviderJob).where(
                    ProviderJob.tenant_id == tenant_id,
                    ProviderJob.task_id == task_id,
                    ProviderJob.execution_id == execution_id,
                    ProviderJob.status == "submitting",
                    ProviderJob.remote_id.is_(None),
                    ProviderJob.is_deleted == 0,
                )
            )
        )
        .scalars()
        .all()
    )
    for job in jobs:
        job.status = "submission_unknown"
        job.error_message = "视频提交过程已中断，厂商是否受理尚不明确；未重新提交，请核对厂商任务和费用。"
