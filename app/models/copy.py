from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Copy(Base, AuditMixin):
    __tablename__ = "ac_copy"
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    bullets: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft")
