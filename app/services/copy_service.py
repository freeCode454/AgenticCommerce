"""
文案服务层 (CopyService)
核心业务: 文案列表查询、详情、人工编辑修改
"""

import logging
from typing import Optional
from sqlalchemy import select, update
from app.services.base import BaseService
from app.models.copy import Copy
from app.models.sku import Sku
from app.models.task import Task
from app.models.compliance import ComplianceReport
from app.services.delivery_content import latest_copy
from app.services.task_queue import TaskConflictError, refresh_batch

logger = logging.getLogger("copy_service")


class CopyService(BaseService):

    async def list_copies(
        self, tenant_id: str, page: int = 1, page_size: int = 10,
        sku_id: Optional[str] = None, task_id: Optional[str] = None,
    ) -> tuple:
        query = select(Copy).where(Copy.tenant_id == tenant_id, Copy.is_deleted == 0)
        if sku_id:
            query = query.where(Copy.sku_id == sku_id)
        if task_id:
            query = query.where(Copy.task_id == task_id)
        query = query.order_by(Copy.create_time.desc())

        items, total = await self.paginate(query, page, page_size)

        result = []
        for c in items:
            sku_res = await self.session.execute(select(Sku.name, Sku.code).where(Sku.id == c.sku_id, Sku.tenant_id == tenant_id, Sku.is_deleted == 0))
            sku_info = sku_res.first()
            result.append({
                "id": c.id, "task_id": c.task_id, "sku_id": c.sku_id,
                "sku_name": sku_info[0] if sku_info else "",
                "sku_code": sku_info[1] if sku_info else "",
                "language": c.language, "title": c.title, "bullets": c.bullets,
                "description": c.description, "keywords": c.keywords,
                "status": c.status,
                "create_time": c.create_time.isoformat() if c.create_time else None,
            })
        return result, total

    async def get_copy(self, tenant_id: str, copy_id: str) -> dict:
        res = await self.session.execute(
            select(Copy).where(Copy.id == copy_id, Copy.tenant_id == tenant_id, Copy.is_deleted == 0)
        )
        c = res.scalar_one_or_none()
        if not c:
            raise ValueError("文案不存在")
        return {
            "id": c.id, "task_id": c.task_id, "sku_id": c.sku_id,
            "language": c.language, "title": c.title, "bullets": c.bullets,
            "description": c.description, "keywords": c.keywords,
            "status": c.status,
            "create_time": c.create_time.isoformat() if c.create_time else None,
        }

    async def update_copy(self, tenant_id: str, copy_id: str, update_data: dict) -> str:
        res = await self.session.execute(
            select(Copy).where(Copy.id == copy_id, Copy.tenant_id == tenant_id, Copy.is_deleted == 0)
        )
        copy_obj = res.scalar_one_or_none()
        if copy_obj is None:
            raise ValueError("文案不存在")
        clean = {k: v for k, v in update_data.items() if v is not None}
        if clean:
            task = (await self.session.execute(select(Task).where(
                Task.id == copy_obj.task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0,
            ).with_for_update())).scalar_one_or_none()
            copy_obj = (await self.session.execute(select(Copy).where(
                Copy.id == copy_id, Copy.tenant_id == tenant_id, Copy.is_deleted == 0,
            ).execution_options(populate_existing=True))).scalar_one_or_none()
            if copy_obj is None:
                raise ValueError("文案不存在")
            current = task is not None and task.execution_id == copy_obj.execution_id
            if current and task.status in {"pending", "running", "retrying"}:
                raise TaskConflictError("任务仍在执行，请等待本次生成结束后编辑文案")
            content_changed = any(
                key != "status" and getattr(copy_obj, key) != value for key, value in clean.items()
            )
            if current and content_changed and await latest_copy(self.session, task) is copy_obj:
                if task.status != "canceled":
                    task.status = "review_required"
                await self.session.execute(update(ComplianceReport).where(
                    ComplianceReport.task_id == copy_obj.task_id, ComplianceReport.tenant_id == tenant_id,
                    ComplianceReport.execution_id == task.execution_id, ComplianceReport.is_deleted == 0,
                ).values(passed=0, status="outdated"))
                await refresh_batch(self.session, tenant_id, task.batch_id)
            await self.session.execute(update(Copy).where(Copy.id == copy_id, Copy.tenant_id == tenant_id, Copy.is_deleted == 0).values(**clean))
            await self.session.commit()
        return copy_id
