from sqlalchemy import String, Integer, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Batch(Base, AuditMixin):
    __tablename__ = "ac_batch"
    __table_args__ = (Index("uq_batch_request", "tenant_id", "request_key", unique=True),)
    request_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
