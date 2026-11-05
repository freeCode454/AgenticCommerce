from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class OperationLog(Base, AuditMixin):
    __tablename__ = "ac_operation_log"
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_name: Mapped[str] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str] = mapped_column(String(32), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
