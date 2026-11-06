"""Readiness checks with bounded I/O and no connection details in responses."""
import asyncio
from sqlalchemy import text
from app.clients.postgres import AsyncSessionLocal
from app.clients.redis import redis_client
from app.clients.minio import minio_client
from app.conf.config import settings


async def dependency_status() -> dict[str, str]:
    async def postgres() -> bool:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
            await session.execute(text("SELECT execution_id FROM ac_task WHERE tenant_id = '__schema_check__' LIMIT 1"))
            await session.execute(text("SELECT request_key FROM ac_task_execution WHERE tenant_id = '__schema_check__' LIMIT 1"))
            await session.execute(text("SELECT state_snapshot FROM ac_task_execution WHERE tenant_id = '__schema_check__' LIMIT 1"))
            await session.execute(text("SELECT remote_id FROM ac_provider_job WHERE tenant_id = '__schema_check__' LIMIT 1"))
        return True

    async def redis() -> bool:
        return bool(await redis_client.ping())

    async def storage() -> bool:
        return await asyncio.to_thread(minio_client.bucket_exists, settings.MINIO_BUCKET)

    async def check(name: str, operation) -> tuple[str, str]:
        try:
            ok = await asyncio.wait_for(operation(), timeout=3)
            return name, "ready" if ok else "unavailable"
        except Exception:
            return name, "unavailable"

    return dict(await asyncio.gather(
        check("postgres", postgres), check("redis", redis), check("storage", storage),
    ))
