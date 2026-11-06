"""A tenant-owned remote video request, with row-bound encrypted credentials."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class ProviderJob(Base, AuditMixin):
    __tablename__ = "ac_provider_job"
    __table_args__ = (
        Index(
            "uq_provider_job_round", "tenant_id", "execution_id", "round", unique=True
        ),
    )
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    execution_id: Mapped[str] = mapped_column(String(32), index=True)
    round: Mapped[int] = mapped_column(Integer)
    provider_id: Mapped[str | None] = mapped_column(String(32))
    adapter: Mapped[str] = mapped_column(String(32), default="dashscope_wan")
    model: Mapped[str] = mapped_column(String(128))
    api_base: Mapped[str] = mapped_column(String(512))
    api_key_enc: Mapped[str] = mapped_column(String(512))
    request_hash: Mapped[str] = mapped_column(String(64))
    remote_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="submitting")
    remote_status: Mapped[str | None] = mapped_column(String(32))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    query_failures: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
