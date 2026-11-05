"""
SQLAlchemy 模型基类与 7 大审计字段规范
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def generate_uuid32() -> str:
    return uuid.uuid4().hex

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class AuditMixin:
    """每张业务表必须包含的 7 个审计字段与租户隔离标识"""
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid32)
    tenant_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(32), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
