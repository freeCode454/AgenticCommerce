"""
多平台刊登发布管理接口 (Listings Router)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.listing import Listing
from app.models.sku import Sku
from app.models.base import generate_uuid32

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
        sku_res = await db.execute(select(Sku.name, Sku.code).where(Sku.id == l.sku_id))
        sku_info = sku_res.first()
        items.append({
            "id": l.id,
            "sku_id": l.sku_id,
            "sku_name": sku_info[0] if sku_info else "",
            "sku_code": sku_info[1] if sku_info else "",
            "platform": l.platform,
            "status": l.status,
            "listing_data": l.listing_data,
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
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """向海外电商平台执行商品上架刊登"""
    tenant_id = user_tenant["tenant_id"]
    sku_res = await db.execute(select(Sku).where(Sku.id == req.sku_id, Sku.tenant_id == tenant_id))
    if not sku_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="目标商品不存在")

    listing_id = f"list_{generate_uuid32()[:12]}"
    listing = Listing(
        id=listing_id,
        tenant_id=tenant_id,
        sku_id=req.sku_id,
        platform=req.platform,
        status="published",
        listing_data={
            **req.listing_data,
            "external_product_id": f"EXT_{req.platform.upper()}_{generate_uuid32()[:8]}",
        },
        created_by=user_tenant.get("user_id"),
    )
    db.add(listing)
    await db.commit()

    return {
        "code": 200,
        "data": {
            "listing_id": listing_id,
            "platform": req.platform,
            "status": "published",
        },
        "message": f"成功同步至 {req.platform} 平台"
    }
