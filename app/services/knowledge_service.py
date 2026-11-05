"""
知识库服务层 (KnowledgeService)
核心业务: 文档入库、向量切片、Embedding、相似度检索
"""

import logging
from typing import Optional
from sqlalchemy import select
from app.services.base import BaseService
from app.models.knowledge import KnowledgeBaseDoc, KnowledgeChunk
from app.models.base import generate_uuid32
from app.clients.provider_factory import ProviderFactory

logger = logging.getLogger("knowledge_service")


class KnowledgeService(BaseService):

    async def list_docs(
        self, tenant_id: str, page: int = 1, page_size: int = 10,
        category: Optional[str] = None,
    ) -> tuple:
        query = select(KnowledgeBaseDoc).where(
            KnowledgeBaseDoc.tenant_id == tenant_id, KnowledgeBaseDoc.is_deleted == 0
        )
        if category:
            query = query.where(KnowledgeBaseDoc.category == category)
        query = query.order_by(KnowledgeBaseDoc.create_time.desc())

        items, total = await self.paginate(query, page, page_size)
        return [
            {
                "id": d.id, "category": d.category, "doc_type": d.doc_type,
                "name": d.name, "vector_status": d.vector_status,
                "create_time": d.create_time.isoformat() if d.create_time else None,
            }
            for d in items
        ], total

    async def create_doc(
        self, tenant_id: str, user_id: str,
        category: str, doc_type: str, name: str, content: str,
    ) -> str:
        """创建文档 + 简易文本切片 + Embedding 向量化"""
        doc_id = f"doc_{generate_uuid32()[:12]}"
        doc = KnowledgeBaseDoc(
            id=doc_id, tenant_id=tenant_id, category=category,
            doc_type=doc_type, name=name, vector_status="indexed",
            created_by=user_id,
        )
        self.session.add(doc)

        # Embedding 计算
        llm_client = ProviderFactory.get_llm_client()
        embedding = await llm_client.get_embedding(content)

        chunk = KnowledgeChunk(
            id=f"chunk_{generate_uuid32()[:12]}",
            tenant_id=tenant_id, doc_id=doc_id, doc_type=doc_type,
            chunk_index=1, content=content, embedding=embedding,
            metadata_json={"name": name, "category": category},
            created_by=user_id,
        )
        self.session.add(chunk)
        await self.session.commit()
        logger.info(f"知识文档创建并向量化: {doc_id}")
        return doc_id

    async def get_doc_detail(self, tenant_id: str, doc_id: str) -> dict:
        res = await self.session.execute(
            select(KnowledgeBaseDoc).where(
                KnowledgeBaseDoc.id == doc_id, KnowledgeBaseDoc.tenant_id == tenant_id
            )
        )
        d = res.scalar_one_or_none()
        if not d:
            raise ValueError("文档不存在")

        chunks_res = await self.session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id)
        )
        chunks = chunks_res.scalars().all()

        return {
            "id": d.id, "category": d.category, "doc_type": d.doc_type,
            "name": d.name, "vector_status": d.vector_status,
            "chunks": [{"id": c.id, "index": c.chunk_index, "content": c.content} for c in chunks],
        }

    async def vector_search(self, tenant_id: str, query_text: str, top_k: int = 3) -> list:
        """向量相似度检索"""
        llm_client = ProviderFactory.get_llm_client()
        q_vec = await llm_client.get_embedding(query_text)

        query = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.tenant_id == tenant_id)
            .order_by(KnowledgeChunk.embedding.cosine_distance(q_vec))
            .limit(top_k)
        )
        result = await self.session.execute(query)
        chunks = result.scalars().all()
        return [{"id": c.id, "content": c.content, "doc_type": c.doc_type} for c in chunks]
