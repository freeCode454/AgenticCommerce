from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, AuditMixin

class User(Base, AuditMixin):
    __tablename__ = "ac_user"
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="operator")
    status: Mapped[str] = mapped_column(String(32), default="active")
