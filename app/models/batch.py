from sqlalchemy import String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Batch(Base, AuditMixin):
    __tablename__ = "ac_batch"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
