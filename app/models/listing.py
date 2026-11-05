from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Listing(Base, AuditMixin):
    __tablename__ = "ac_listing"
    sku_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    listing_data: Mapped[dict] = mapped_column(JSON, default=dict)
