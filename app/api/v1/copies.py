"""
文案库管理接口 (Copy Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.copy_service import CopyService

router = APIRouter(prefix="/copies", tags=["文案管理"])

class CopyUpdateRequest(BaseModel):
    title: Optional[str] = None
    bullets: Optional[List[str]] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    status: Optional[str] = None


@router.get("")
async def list_copies(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sku_id: Optional[str] = None,
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页查询文案列表"""
    svc = CopyService(db)
    items, total = await svc.list_copies(user_tenant["tenant_id"], page, page_size, sku_id, task_id)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.get("/{copy_id}")
async def get_copy(
    copy_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取单个文案详情"""
    svc = CopyService(db)
    try:
        result = await svc.get_copy(user_tenant["tenant_id"], copy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}


@router.put("/{copy_id}")
async def update_copy(
    copy_id: str,
    req: CopyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """人工修改并调整文案"""
    svc = CopyService(db)
    try:
        result_id = await svc.update_copy(user_tenant["tenant_id"], copy_id, req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": {"id": result_id}, "message": "文案保存成功"}
