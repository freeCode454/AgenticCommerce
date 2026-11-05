"""
知识库与 RAG 向量管理接口 (Knowledge Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["知识库RAG管理"])

class DocCreateRequest(BaseModel):
    category: str
    doc_type: str
    name: str
    content: str

class QueryTestRequest(BaseModel):
    query_text: str
    top_k: int = 3


@router.get("/docs")
async def list_docs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页获取知识库文档列表"""
    svc = KnowledgeService(db)
    items, total = await svc.list_docs(user_tenant["tenant_id"], page, page_size, category)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.post("/docs")
async def create_doc(
    req: DocCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """录入新知识库文档并执行向量切片"""
    svc = KnowledgeService(db)
    doc_id = await svc.create_doc(
        tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
        category=req.category, doc_type=req.doc_type, name=req.name, content=req.content,
    )
    return {"code": 200, "data": {"doc_id": doc_id}, "message": "知识库文档创建并向量化成功"}


@router.get("/docs/{doc_id}")
async def get_doc_detail(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取知识库文档详情与对应分块"""
    svc = KnowledgeService(db)
    try:
        result = await svc.get_doc_detail(user_tenant["tenant_id"], doc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}


@router.post("/query")
async def test_vector_search(
    req: QueryTestRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """测试向量相似度召回 (RAG 调试)"""
    svc = KnowledgeService(db)
    results = await svc.vector_search(user_tenant["tenant_id"], req.query_text, req.top_k)
    return {"code": 200, "data": {"query": req.query_text, "results": results}, "message": "检索完成"}
