from sqlalchemy import String, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from .base import Base, AuditMixin

class KnowledgeBaseDoc(Base, AuditMixin):
    __tablename__ = "ac_knowledge_base_doc"
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    vector_status: Mapped[str] = mapped_column(String(32), default="pending")

class KnowledgeChunk(Base, AuditMixin):
    __tablename__ = "ac_knowledge_chunk"
    doc_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1024), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
