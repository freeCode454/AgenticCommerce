from sqlalchemy import select
from .base import BaseRepository
from app.models.knowledge import KnowledgeChunk

class KnowledgeRepository(BaseRepository[KnowledgeChunk]):
    def __init__(self, session):
        super().__init__(KnowledgeChunk, session)

    async def search_vectors(self, tenant_id: str, query_vector: list, limit: int = 5, threshold: float = 0.5):
        """基于 pgvector 进行 RAG 余弦相似度向量检索"""
        stmt = select(self.model_class).where(
            self.model_class.tenant_id == tenant_id,
            self.model_class.is_deleted == 0,
            # 余弦距离 (Cosine Distance)，距离越小越相似
            self.model_class.embedding.cosine_distance(query_vector) < threshold
        ).order_by(
            self.model_class.embedding.cosine_distance(query_vector)
        ).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()
