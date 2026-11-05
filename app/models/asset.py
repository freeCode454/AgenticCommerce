from sqlalchemy import String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Asset(Base, AuditMixin):
    __tablename__ = "ac_asset"
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False) # image / video
    sub_type: Mapped[str] = mapped_column(String(32), nullable=True) # main / scene / detail
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    is_mock: Mapped[int] = mapped_column(default=0)
