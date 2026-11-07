"""
素材资产库管理接口 (Asset Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from collections.abc import Iterator
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.asset import Asset
from app.services.asset_service import AssetService
from app.services.media_archive import MEDIA_EXTENSIONS, archive_metadata_valid, iter_object

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
    try:
        asset_id = await svc.create_asset(
            tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
            sku_id=req.sku_id, type=req.type, url=req.url,
            task_id=req.task_id, sub_type=req.sub_type, meta=req.meta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {"code": 200, "data": {"id": asset_id}, "message": "素材登记成功"}


@router.get("/{asset_id}/file")
async def download_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
) -> StreamingResponse:
    asset = (await db.execute(select(Asset).where(
        Asset.id == asset_id, Asset.tenant_id == user_tenant["tenant_id"], Asset.is_deleted == 0,
    ))).scalar_one_or_none()
    if asset is None or not asset.archive_key:
        raise HTTPException(status_code=404, detail="归档素材不存在")
    size, content_type = asset.archive_size or 0, asset.archive_content_type or ""
    if not archive_metadata_valid(size, content_type, asset.type):
        raise HTTPException(status_code=503, detail="归档素材暂不可用")

    chunks = iter_object(asset.archive_key, size)
    try:
        first = await run_in_threadpool(next, chunks, b"")
    except Exception:
        raise HTTPException(status_code=503, detail="归档素材暂不可用") from None

    def stream() -> Iterator[bytes]:
        yield first
        yield from chunks

    extension = MEDIA_EXTENSIONS[content_type]
    return StreamingResponse(
        stream(), media_type=content_type, background=BackgroundTask(chunks.close),
        headers={
            "Content-Length": str(size), "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="asset.{extension}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


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
