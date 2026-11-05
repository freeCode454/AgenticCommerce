from sqlalchemy import String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Task(Base, AuditMixin):
    __tablename__ = "ac_task"
    batch_id: Mapped[str] = mapped_column(String(32), nullable=True, index=True)
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    current_node: Mapped[str] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(String(1024), nullable=True)
