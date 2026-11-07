"""Save generated media independently of the paid workflow."""

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import logging
import re
import socket
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

import httpx
from minio.error import S3Error
from sqlalchemy import or_, select

from app.clients.minio import create_minio_client, ensure_bucket_exists
from app.clients.postgres import AsyncSessionLocal
from app.conf.config import settings
from app.models.asset import Asset
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
minio_client = create_minio_client(15)
CHUNK_SIZE = 256 * 1024
MEDIA_LIMITS = {"image": 20 * 1024**2, "video": 100 * 1024**2}
MEDIA_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
}
OSS_HOST = re.compile(
    r"[a-z0-9][a-z0-9-]*\.oss-(?:cn-[a-z0-9-]+|accelerate)\.aliyuncs\.com"
)


class ArchiveError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


async def source_request(source: str) -> tuple[httpx.URL, str]:
    try:
        url = httpx.URL(source)
    except (httpx.InvalidURL, ValueError):
        raise ArchiveError("素材来源地址无效") from None
    host = url.host
    if (
        url.scheme != "https" or not OSS_HOST.fullmatch(host)
        or url.userinfo or url.port not in {None, 443} or url.fragment
    ):
        raise ArchiveError("素材来源不在自动归档范围内")
    addresses = await asyncio.get_running_loop().getaddrinfo(
        host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM,
    )
    ips = [ipaddress.IPv4Address(address[4][0]) for address in addresses]
    if not ips or any(not ip.is_global or ip.is_multicast for ip in ips):
        raise ArchiveError("素材来源地址不可归档")
    # Pin the resolved address while keeping the OSS signature and TLS identity.
    return url.copy_with(host=str(ips[0])), host


def media_type(header: bytes, kind: str) -> str:
    if kind == "image":
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"
    if kind == "video":
        if header[4:8] == b"ftyp":
            return "video/mp4"
        if header.startswith(b"\x1a\x45\xdf\xa3"):
            return "video/webm"
    raise ArchiveError("素材文件格式不受支持")


async def fetch_source(source: str, kind: str, file: BinaryIO) -> tuple[int, str]:
    limit = MEDIA_LIMITS[kind]
    try:
        async with asyncio.timeout(90):
            url, host = await source_request(source)
            request = httpx.Request(
                "GET", url,
                headers={"Host": host, "Accept-Encoding": "identity"},
                extensions={"sni_hostname": host, "timeout": httpx.Timeout(10).as_dict()},
            )
            # Use the transport directly so HTTPX does not log signed query strings.
            async with httpx.AsyncHTTPTransport(trust_env=False) as transport:
                response = await transport.handle_async_request(request)
                try:
                    if response.status_code != 200:
                        if response.status_code in {401, 403, 404, 410}:
                            raise ArchiveError("素材来源已失效或无法访问")
                        raise ArchiveError(
                            "素材来源暂不可用",
                            retryable=response.status_code >= 500 or response.status_code in {408, 429},
                        )
                    size = 0
                    async for chunk in response.aiter_raw(CHUNK_SIZE):
                        size += len(chunk)
                        if size > limit:
                            raise ArchiveError("素材文件超过归档大小限制")
                        file.write(chunk)
                finally:
                    await response.aclose()
    except (httpx.RequestError, OSError, TimeoutError):
        raise ArchiveError("下载素材暂时失败", retryable=True) from None
    file.seek(0)
    content_type = media_type(file.read(16), kind)
    file.seek(0)
    return size, content_type


def existing_object(key: str) -> tuple[int, str] | None:
    ensure_bucket_exists(settings.MINIO_BUCKET, client=minio_client)
    try:
        result = minio_client.stat_object(settings.MINIO_BUCKET, key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
            return None
        raise
    return result.size or 0, result.content_type or ""


def archive_metadata_valid(size: int, content_type: str, kind: str) -> bool:
    return (
        content_type in MEDIA_EXTENSIONS and content_type.startswith(f"{kind}/")
        and 0 < size <= MEDIA_LIMITS.get(kind, 0)
    )


async def store_asset(asset: Asset) -> None:
    digest = hashlib.sha256(f"{asset.tenant_id}/{asset.id}".encode()).hexdigest()
    key = f"generated/{digest}"
    try:
        metadata = await asyncio.to_thread(existing_object, key)
        if metadata is None or not archive_metadata_valid(*metadata, asset.type):
            with SpooledTemporaryFile(max_size=2 * 1024**2) as file:
                size, content_type = await fetch_source(asset.url, asset.type, file)
                upload = asyncio.create_task(asyncio.to_thread(
                    minio_client.put_object, settings.MINIO_BUCKET, key, file, size,
                    content_type=content_type, num_parallel_uploads=1,
                ))
                try:
                    await asyncio.shield(upload)
                except asyncio.CancelledError:
                    # The upload thread still owns the temporary file.
                    await asyncio.gather(upload, return_exceptions=True)
                    raise
                metadata = size, content_type
        asset.archive_key = key
        asset.archive_size, asset.archive_content_type = metadata
        asset.archive_error = asset.archive_retry_at = None
    except ArchiveError:
        raise
    except Exception:
        raise ArchiveError("对象存储暂不可用", retryable=True) from None


async def archive_next(tenant_id: str) -> bool:
    async with AsyncSessionLocal.begin() as db:
        asset = (await db.execute(
            select(Asset)
            .where(
                Asset.tenant_id == tenant_id, Asset.is_deleted == 0,
                Asset.execution_id.is_not(None), Asset.is_mock == 0,
                Asset.status == "completed", Asset.type.in_(MEDIA_LIMITS),
                Asset.archive_key.is_(None),
                or_(Asset.archive_error.is_(None), Asset.archive_retry_at <= datetime.now(timezone.utc)),
            )
            .order_by(Asset.create_time, Asset.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if asset is None:
            return False
        try:
            await store_asset(asset)
        except ArchiveError as exc:
            asset.archive_attempts += 1
            asset.archive_error = str(exc)
            asset.archive_retry_at = (
                datetime.now(timezone.utc) + timedelta(seconds=10 * 2 ** min(asset.archive_attempts, 8))
                if exc.retryable else None
            )
        return True


async def archive_loop() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                tenants = (await db.scalars(select(Tenant.id).where(
                    Tenant.status == "active", Tenant.is_deleted == 0,
                ))).all()
            processed = False
            for tenant_id in tenants:
                if await archive_next(tenant_id):
                    processed = True
            if processed:
                continue
        except Exception as exc:
            logger.warning("Archive worker will retry (%s)", type(exc).__name__)
        await asyncio.sleep(5)


def iter_object(key: str, size: int) -> Iterator[bytes]:
    response = minio_client.get_object(settings.MINIO_BUCKET, key)
    try:
        remaining = size
        for chunk in response.stream(CHUNK_SIZE):
            remaining -= len(chunk)
            if remaining < 0:
                raise OSError("Archived media size changed")
            yield chunk
        if remaining:
            raise OSError("Archived media is incomplete")
    finally:
        response.close()
        response.release_conn()
