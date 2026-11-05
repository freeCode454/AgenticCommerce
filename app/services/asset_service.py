"""
素材资产服务层 (AssetService)
核心业务: 素材的查询、手动上传登记、删除
"""

import logging
from typing import Optional
from sqlalchemy import select, update
from app.services.base import BaseService
from app.models.asset import Asset
from app.models.sku import Sku

logger = logging.getLogger("asset_service")


class AssetService(BaseService):

    async def list_assets(
        self, tenant_id: str, page: int = 1, page_size: int = 12,
        type: Optional[str] = None, sub_type: Optional[str] = None,
        sku_id: Optional[str] = None, task_id: Optional[str] = None,
    ) -> tuple:
        query = select(Asset).where(Asset.tenant_id == tenant_id, Asset.is_deleted == 0)
        if type:
            query = query.where(Asset.type == type)
        if sub_type:
            query = query.where(Asset.sub_type == sub_type)
        if sku_id:
            query = query.where(Asset.sku_id == sku_id)
        if task_id:
            query = query.where(Asset.task_id == task_id)
        query = query.order_by(Asset.create_time.desc())

        items, total = await self.paginate(query, page, page_size)

        result = []
        for a in items:
            sku_res = await self.session.execute(select(Sku.name, Sku.code).where(Sku.id == a.sku_id))
            sku_info = sku_res.first()
            result.append({
                "id": a.id, "task_id": a.task_id, "sku_id": a.sku_id,
                "sku_name": sku_info[0] if sku_info else "",
                "sku_code": sku_info[1] if sku_info else "",
                "type": a.type, "sub_type": a.sub_type, "url": a.url,
                "meta": a.meta, "status": a.status, "is_mock": a.is_mock,
                "create_time": a.create_time.isoformat() if a.create_time else None,
            })
        return result, total

    async def create_asset(
        self, tenant_id: str, user_id: str,
        sku_id: str, type: str, url: str,
        task_id: str = "manual_upload", sub_type: str = "main", meta: dict = None,
    ) -> str:
        asset = Asset(
            tenant_id=tenant_id, sku_id=sku_id, task_id=task_id or "manual",
            type=type, sub_type=sub_type, url=url, meta=meta or {},
            status="completed", is_mock=0, created_by=user_id,
        )
        self.session.add(asset)
        await self.session.commit()
        await self.session.refresh(asset)
        return asset.id

    async def delete_asset(self, tenant_id: str, asset_id: str) -> str:
        await self.session.execute(
            update(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id).values(is_deleted=1)
        )
        await self.session.commit()
        return asset_id
