"""Persist submission intent and the remote ID before querying an accepted job."""

from datetime import timedelta

from sqlalchemy import select

from app.clients.postgres import AsyncSessionLocal
from app.clients.wan_video import (
    RemoteVideoPending,
    SubmissionUnknownError,
    VideoProviderError,
    VideoQueryError,
)
from app.conf.config import settings
from app.core.provider_context import active_providers
from app.core.provider_keys import decrypt_api_key, encrypt_api_key
from app.core.task_execution import active_execution, fence_execution
from app.models.base import generate_uuid32, utc_now
from app.models.provider_job import ProviderJob
from app.services.task_queue import request_hash


async def owned_job(session, context, round_number: int):
    return (
        await session.execute(
            select(ProviderJob).where(
                ProviderJob.tenant_id == context.tenant_id,
                ProviderJob.task_id == context.task_id,
                ProviderJob.execution_id == context.execution_id,
                ProviderJob.round == round_number,
                ProviderJob.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()


async def generate_durable_video(
    client=None,
    *,
    prompt: str,
    duration: int,
    aspect_ratio: str,
    image_url: str | None,
    round_number: int,
) -> dict:
    context = active_execution.get()
    if context is None:
        raise VideoProviderError("持久化视频生成缺少任务执行身份。")
    payload = {
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "image_url": image_url,
    }
    fingerprint = request_hash(payload)
    async with AsyncSessionLocal() as session:
        await fence_execution(session)
        job = await owned_job(session, context, round_number)
        created = job is None
        if created:
            if client is None:
                from app.clients.provider_factory import ProviderFactory

                client = ProviderFactory.get_video_client("kling")
            if not isinstance(client.api_key, str) or not client.api_key.strip():
                raise VideoProviderError("视频模型凭据缺失，未提交生成。")
            job_id = generate_uuid32()
            runtime = active_providers.get()
            binding = runtime.get("video") if runtime else None
            job = ProviderJob(
                id=job_id,
                tenant_id=context.tenant_id,
                task_id=context.task_id,
                execution_id=context.execution_id,
                round=round_number,
                provider_id=binding.provider_id if binding else None,
                model=client.model or "wan3.0-video",
                api_base=client.api_base,
                api_key_enc=encrypt_api_key(
                    client.api_key,
                    context.tenant_id,
                    "video-job:" + job_id,
                    settings.PROVIDER_ENCRYPTION_KEY,
                ),
                request_hash=fingerprint,
                status="submitting",
                expires_at=utc_now() + timedelta(hours=24),
            )
            session.add(job)
            await session.commit()  # Intent must survive a crash during POST.
        elif job.request_hash != fingerprint:
            raise VideoProviderError("已保存的视频请求与恢复状态不一致，未提交新请求。")
        if not created and job.status in ("submitting", "submission_unknown"):
            raise SubmissionUnknownError(
                "视频提交结果不明，未重新提交；请核对厂商任务和费用。"
            )
        if job.status in ("failed", "canceled", "unknown"):
            raise VideoProviderError(
                job.error_message or "远端视频任务已终止，未重新提交。"
            )
        if job.status == "succeeded":
            if job.expires_at <= utc_now():
                job.status, job.remote_status = "unknown", "UNKNOWN"
                job.error_message = "视频临时结果可能已过期，请核对厂商结果；未重新提交。"
                await session.commit()
                raise VideoProviderError(job.error_message)
            return {**job.result, "provider_job_id": job.id}
        if not created:
            # Freeze the original account/endpoint/model; changing tenant defaults cannot reroute a query.
            from app.clients.provider_factory import KlingVideoClient

            client = KlingVideoClient(
                decrypt_api_key(
                    job.api_key_enc,
                    context.tenant_id,
                    "video-job:" + job.id,
                    settings.PROVIDER_ENCRYPTION_KEY,
                ),
                job.model,
                api_base=job.api_base,
            )
        job_id, remote_id = job.id, job.remote_id

    if created:
        try:
            submitted = await client.submit_video(**payload)
            from app.clients.wan_video import valid_remote_id

            remote_id = valid_remote_id(submitted.get("task_id"))
        except (VideoProviderError, ValueError, TypeError, AttributeError) as error:
            async with AsyncSessionLocal() as session:
                await fence_execution(session)
                job = await owned_job(session, context, round_number)
                job.status = (
                    "submission_unknown"
                    if isinstance(error, SubmissionUnknownError)
                    else "failed"
                )
                job.error_message = (
                    str(error)
                    if isinstance(error, VideoProviderError)
                    else "视频提交响应无效，未再次提交。"
                )
                await session.commit()
            raise
        async with AsyncSessionLocal() as session:
            await fence_execution(session)
            job = await owned_job(session, context, round_number)
            job.remote_id, job.status, job.remote_status = (
                remote_id,
                "submitted",
                "PENDING",
            )
            await session.commit()  # Persist ID before the first GET.

    async with AsyncSessionLocal() as session:
        await fence_execution(session)
        job = await owned_job(session, context, round_number)
        if job.expires_at <= utc_now():
            job.status, job.remote_status = "unknown", "UNKNOWN"
            job.error_message = (
                "远端视频任务已超过查询有效期，未重新提交；请核对厂商记录。"
            )
            await session.commit()
            raise VideoProviderError(job.error_message)
    try:
        result = await client.query_video(remote_id)
    except VideoQueryError as error:
        async with AsyncSessionLocal() as session:
            await fence_execution(session)
            job = await owned_job(session, context, round_number)
            job.query_failures += 1
            job.error_message = str(error)
            await session.commit()
        raise RemoteVideoPending() from None

    async with AsyncSessionLocal() as session:
        await fence_execution(session)
        job = await owned_job(session, context, round_number)
        status = result["task_status"]
        job.remote_status, job.error_message = status, None
        if status in ("PENDING", "RUNNING"):
            job.status = status.lower()
            await session.commit()
            raise RemoteVideoPending()
        if status != "SUCCEEDED":
            job.status, job.finished_at = status.lower(), utc_now()
            job.error_message = (
                "远端视频任务失败、取消或已过期，未重新提交；请核对厂商记录。"
            )
            await session.commit()
            raise VideoProviderError(job.error_message)
        job.status, job.finished_at = "succeeded", utc_now()
        # Deliberately exclude raw provider bodies and credentials.
        job.result = {
            key: result[key]
            for key in ("video_url", "usage", "billing_status")
            if key in result
        }
        job.result.update(
            task_id=remote_id,
            model=job.model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            cost=0.0,
            is_mock=0,
            billing_status="not_reported",
            expires_at=job.expires_at.isoformat(),
        )
        await session.commit()
        return {**job.result, "provider_job_id": job_id}
