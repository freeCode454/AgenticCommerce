"""
MinIO 对象存储客户端初始化与桶管理
"""

from minio import Minio
from app.conf.config import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)

def ensure_bucket_exists(bucket_name: str = settings.MINIO_BUCKET):
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)
