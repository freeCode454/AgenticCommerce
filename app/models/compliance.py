from datetime import datetime

from sqlalchemy import DateTime, String, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class ComplianceReport(Base, AuditMixin):
    __tablename__ = "ac_compliance_report"
    execution_id: Mapped[str | None] = mapped_column(String(32), index=True)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=100.0)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    violations: Mapped[list] = mapped_column(JSON, default=list)
    passed: Mapped[int] = mapped_column(Integer, default=1)
    suggestions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="passed")
    request_key: Mapped[str | None] = mapped_column(String(128))
    human_decision: Mapped[str | None] = mapped_column(String(16))
    human_reviewer_id: Mapped[str | None] = mapped_column(String(32))
    human_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    human_note: Mapped[str | None] = mapped_column(String(1000))
