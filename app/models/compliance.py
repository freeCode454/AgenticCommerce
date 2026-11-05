from sqlalchemy import String, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class ComplianceReport(Base, AuditMixin):
    __tablename__ = "ac_compliance_report"
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=100.0)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    violations: Mapped[list] = mapped_column(JSON, default=list)
    passed: Mapped[int] = mapped_column(Integer, default=1)
    suggestions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="passed")
