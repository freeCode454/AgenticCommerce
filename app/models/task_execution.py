"""Durable task attempts; no physical foreign keys or credentials."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class TaskExecution(Base, AuditMixin):
    __tablename__ = "ac_task_execution"
    __table_args__ = (
        Index(
            "uq_execution_request", "tenant_id", "task_id", "request_key", unique=True
        ),
        Index(
            "uq_task_execution_active",
            "tenant_id",
            "task_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'running') AND is_deleted = 0"
            ),
        ),
    )

    task_id: Mapped[str] = mapped_column(String(32), index=True)
    request_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(1024))
    state_snapshot: Mapped[dict | None] = mapped_column(JSON)
    provider_snapshot_enc: Mapped[dict | None] = mapped_column(JSON)
    next_node: Mapped[str | None] = mapped_column(String(64))
    in_flight_node: Mapped[str | None] = mapped_column(String(64))
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
