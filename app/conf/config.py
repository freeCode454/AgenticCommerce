"""
AgenticCommerce 全局配置类 (基于 Pydantic Settings)
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 基础配置
    APP_ENV: str = "dev"
    APP_NAME: str = "AgenticCommerce"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8002
    DEBUG: bool = True

    # 安全配置
    AUTH_ENABLED: bool = True
    SECRET_KEY: str = "agentic-commerce-dev-secret-key-change-it-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 跨域与主机白名单
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"]
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1", "agentic-backend"]

    # PostgreSQL 16
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5434
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "agentic_commerce"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Redis 7
    REDIS_PORT: int = 6381
    REDIS_URL: str = "redis://127.0.0.1:6381/0"

    # MinIO
    MINIO_API_PORT: int = 9010
    MINIO_CONSOLE_PORT: int = 9011
    MINIO_ENDPOINT: str = "127.0.0.1:9010"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "agentic-assets"
    MINIO_SECURE: bool = False

    # 业务规则
    ALLOW_MOCK_ASSETS: bool = True
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.5
    MAX_QUALITY_RETRIES: int = 2

    # 模型 Key
    DASHSCOPE_API_KEY: str = ""
    WANX_API_KEY: str = ""
    KLING_API_KEY: str = ""
    KLING_ACCESS_KEY_ID: str = ""
    KLING_ACCESS_KEY_SECRET: str = ""
    OPENAI_API_KEY: str = ""
    SENSENOVA_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
