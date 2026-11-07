"""
多平台刊登发布管理接口 (Listings Router)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.listing import Listing
from app.models.sku import Sku

router = APIRouter(prefix="/listings", tags=["跨境多平台刊登"])

class ListingPublishRequest(BaseModel):
    sku_id: str
    platform: str  # amazon / shopify / tiktok
    listing_data: Dict[str, Any]

@router.get("")
async def list_listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页获取刊登发布记录"""
    tenant_id = user_tenant["tenant_id"]
    query = select(Listing).where(Listing.tenant_id == tenant_id, Listing.is_deleted == 0)

    if platform:
        query = query.where(Listing.platform == platform)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Listing.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    listings = result.scalars().all()

    items = []
    for l in listings:
        sku_res = await db.execute(select(Sku.name, Sku.code).where(
            Sku.id == l.sku_id, Sku.tenant_id == tenant_id, Sku.is_deleted == 0,
        ))
        sku_info = sku_res.first()
        listing_data = dict(l.listing_data or {})
        external_id = listing_data.get("external_product_id")
        if isinstance(external_id, str) and external_id.startswith("EXT_"):
            listing_data.pop("external_product_id")
        items.append({
            "id": l.id,
            "sku_id": l.sku_id,
            "sku_name": sku_info[0] if sku_info else "",
            "sku_code": sku_info[1] if sku_info else "",
            "platform": l.platform,
            "status": "local_record" if l.status == "published" else l.status,
            "listing_data": listing_data,
            "create_time": l.create_time.isoformat() if l.create_time else None,
        })

    return {
        "code": 200,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
        "message": "获取成功"
    }

@router.post("")
async def publish_listing(
    req: ListingPublishRequest,
    user_tenant: dict = Depends(get_current_user_and_tenant),
) -> None:
    """保留接口契约，明确拒绝尚未接通的平台发布。"""
    raise HTTPException(status_code=501, detail="平台自动刊登尚未开放，请下载交付包后手动刊登。")
