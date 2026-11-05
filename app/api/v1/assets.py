"""
素材资产库管理接口 (Asset Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["素材资产管理"])

class AssetCreateRequest(BaseModel):
    sku_id: str
    task_id: Optional[str] = "manual_upload"
    type: str  # image / video
    sub_type: Optional[str] = "main"
    url: str
    meta: dict = {}


@router.get("")
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    type: Optional[str] = None,
    sub_type: Optional[str] = None,
    sku_id: Optional[str] = None,
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页查询视觉与视频资产"""
    svc = AssetService(db)
    items, total = await svc.list_assets(user_tenant["tenant_id"], page, page_size, type, sub_type, sku_id, task_id)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.post("")
async def create_asset(
    req: AssetCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """手动上传/登记素材"""
    svc = AssetService(db)
    asset_id = await svc.create_asset(
        tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
        sku_id=req.sku_id, type=req.type, url=req.url,
        task_id=req.task_id, sub_type=req.sub_type, meta=req.meta,
    )
    return {"code": 200, "data": {"id": asset_id}, "message": "素材登记成功"}


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """删除素材"""
    svc = AssetService(db)
    result_id = await svc.delete_asset(user_tenant["tenant_id"], asset_id)
    return {"code": 200, "data": {"id": result_id}, "message": "删除成功"}
