from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class Provider(Base, AuditMixin):
    __tablename__ = "ac_provider"
    type: Mapped[str] = mapped_column(String(32), nullable=False) # llm / image / video
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[int] = mapped_column(default=0)
