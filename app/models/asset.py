from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Integer, JSON, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Asset(Base, AuditMixin):
    __tablename__ = "ac_asset"
    __table_args__ = (Index("uq_asset_provider_job", "tenant_id", "provider_job_id", unique=True),)
    provider_job_id: Mapped[str | None] = mapped_column(String(32))
    execution_id: Mapped[str | None] = mapped_column(String(32), index=True)
    generation_round: Mapped[int | None] = mapped_column(Integer)
    archive_key: Mapped[str | None] = mapped_column(String(256))
    archive_content_type: Mapped[str | None] = mapped_column(String(64))
    archive_size: Mapped[int | None] = mapped_column(BigInteger)
    archive_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    archive_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_error: Mapped[str | None] = mapped_column(String(256))
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False) # image / video
    sub_type: Mapped[str] = mapped_column(String(32), nullable=True) # main / scene / detail
    url: Mapped[str] = mapped_column(String(8192), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    is_mock: Mapped[int] = mapped_column(default=0)

    @property
    def display_url(self) -> str:
        return f"/api/v1/assets/{self.id}/file" if self.archive_key else self.url

    @property
    def archive_status(self) -> str:
        if self.archive_key:
            return "stored"
        if self.archive_error:
            return "retrying" if self.archive_retry_at else "failed"
        if self.execution_id and not self.is_mock and self.type in {"image", "video"}:
            return "pending"
        return "external"
