"""
MinIO 对象存储客户端初始化与桶管理
"""

from minio import Minio
from app.conf.config import settings
import urllib3

def create_minio_client(read_timeout: float) -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        http_client=urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2, read=read_timeout), retries=False,
        ),
    )


minio_client = create_minio_client(2)


def ensure_bucket_exists(bucket_name: str = settings.MINIO_BUCKET, *, client: Minio = minio_client) -> None:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
