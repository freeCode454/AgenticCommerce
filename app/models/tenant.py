from sqlalchemy import String, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, generate_uuid32, utc_now
from datetime import datetime
from sqlalchemy import DateTime

class Tenant(Base):
    __tablename__ = "ac_tenant"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid32)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    plan: Mapped[str] = mapped_column(String(32), default="standard")
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    is_deleted: Mapped[int] = mapped_column(SmallInteger, default=0)
