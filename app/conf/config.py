"""
AgenticCommerce 全局配置类 (基于 Pydantic Settings)
"""

from typing import List, Literal, Self
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

DEV_SECRET = "agentic-commerce-dev-secret-key-change-it-in-production-2026"

class Settings(BaseSettings):
    # 基础配置
    APP_ENV: str = "dev"
    APP_NAME: str = "AgenticCommerce"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = Field(8002, ge=1, le=65535)
    FRONTEND_PORT: int = Field(5174, ge=1, le=65535)
    DEBUG: bool = True

    # 安全配置
    AUTH_ENABLED: bool = True
    SECRET_KEY: str = Field(DEV_SECRET, repr=False)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 跨域与主机白名单
    CORS_ORIGINS: List[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1", "agentic-backend"]

    # PostgreSQL 16
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5435
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = Field("postgres", repr=False)
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
    MINIO_SECRET_KEY: str = Field("minioadmin", repr=False)
    MINIO_BUCKET: str = "agentic-assets"
    MINIO_SECURE: bool = False

    # 业务规则
    ALLOW_MOCK_ASSETS: bool = True
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.5
    MAX_QUALITY_RETRIES: int = 2
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@agentic.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = Field("", repr=False)

    # 模型 Key
    DASHSCOPE_API_KEY: str = Field("", repr=False)
    WANX_API_KEY: str = Field("", repr=False)
    KLING_API_KEY: str = Field("", repr=False)
    KLING_ACCESS_KEY_ID: str = Field("", repr=False)
    KLING_ACCESS_KEY_SECRET: str = Field("", repr=False)
    OPENAI_API_KEY: str = Field("", repr=False)
    SENSENOVA_API_KEY: str = Field("", repr=False)

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() not in {"dev", "test"}

    @model_validator(mode="after")
    def validate_security(self) -> Self:
        if not self.AUTH_ENABLED:
            raise ValueError("Authentication is required; AUTH_ENABLED must be true")
        if self.is_production:
            if self.DEBUG or self.ALLOW_MOCK_ASSETS:
                raise ValueError("Production requires DEBUG=false and ALLOW_MOCK_ASSETS=false")
            if self.SECRET_KEY == DEV_SECRET or len(self.SECRET_KEY.encode()) < 32:
                raise ValueError("Production requires an independent SECRET_KEY of at least 32 bytes")
            if self.POSTGRES_PASSWORD in {"", "postgres"} or self.MINIO_SECRET_KEY in {"", "minioadmin"}:
                raise ValueError("Production requires independent database and storage credentials")
            if "*" in self.CORS_ORIGINS or "*" in self.TRUSTED_HOSTS:
                raise ValueError("Production requires explicit origins and trusted hosts")
        return self

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+asyncpg", username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD, host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT, database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

settings = Settings()
