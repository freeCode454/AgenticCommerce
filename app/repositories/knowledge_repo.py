from sqlalchemy import Select, or_, select
from sqlalchemy.sql.elements import ColumnElement
from .base import BaseRepository
from app.models.knowledge import KnowledgeChunk


def embedding_model_filter(model: str) -> ColumnElement[bool]:
    recorded = KnowledgeChunk.metadata_json["embedding_model"].as_string()
    if model == "text-embedding-v4":
        return or_(recorded == model, recorded.is_(None))
    return recorded == model

class KnowledgeRepository(BaseRepository[KnowledgeChunk]):
    def __init__(self, session):
        super().__init__(KnowledgeChunk, session)

    def _vector_candidates(self, tenant_id: str, embedding_model: str) -> Select[tuple[KnowledgeChunk]]:
        return select(self.model_class).where(
            self.model_class.tenant_id == tenant_id,
            self.model_class.is_deleted == 0,
            self.model_class.embedding.is_not(None),
            embedding_model_filter(embedding_model),
        )

    async def has_searchable_chunks(self, tenant_id: str, embedding_model: str) -> bool:
        return bool(await self.session.scalar(select(self._vector_candidates(tenant_id, embedding_model).exists())))

    async def search_vectors(self, tenant_id: str, query_vector: list, limit: int = 5, threshold: float = 0.5, embedding_model: str = "text-embedding-v4"):
        """基于 pgvector 进行 RAG 余弦相似度向量检索"""
        distance = self.model_class.embedding.cosine_distance(query_vector)
        stmt = self._vector_candidates(tenant_id, embedding_model).where(distance < threshold).order_by(distance).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()
