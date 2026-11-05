"""
批次任务服务层 (BatchService)
核心业务: 批次创建、批量任务生成
"""

import logging
from typing import List, Dict, Any
from sqlalchemy import select
from app.services.base import BaseService
from app.models.batch import Batch
from app.models.task import Task
from app.models.base import generate_uuid32

logger = logging.getLogger("batch_service")


class BatchService(BaseService):

    async def list_batches(self, tenant_id: str, page: int = 1, page_size: int = 10) -> tuple:
        query = select(Batch).where(Batch.tenant_id == tenant_id, Batch.is_deleted == 0)
        query = query.order_by(Batch.create_time.desc())
        items, total = await self.paginate(query, page, page_size)
        return [
            {
                "id": b.id, "name": b.name, "status": b.status,
                "total_count": b.total_count, "completed_count": b.completed_count,
                "failed_count": b.failed_count, "config": b.config,
                "create_time": b.create_time.isoformat() if b.create_time else None,
            }
            for b in items
        ], total

    async def create_batch(
        self, tenant_id: str, user_id: str,
        name: str, sku_ids: List[str], config: Dict[str, Any] = None,
    ) -> dict:
        """创建批次 + 批量创建 Task 记录，返回各 task 信息供路由层调度工作流"""
        if not sku_ids:
            raise ValueError("sku_ids 不能为空")

        batch_id = f"batch_{generate_uuid32()[:12]}"
        batch = Batch(
            id=batch_id, tenant_id=tenant_id, name=name,
            status="running", total_count=len(sku_ids),
            completed_count=0, failed_count=0,
            config=config or {}, created_by=user_id,
        )
        self.session.add(batch)

        task_infos = []
        for sku_id in sku_ids:
            task_id = f"task_{generate_uuid32()[:12]}"
            task = Task(
                id=task_id, tenant_id=tenant_id, sku_id=sku_id,
                batch_id=batch_id, status="running", current_node="orchestrator",
                retry_count=0, config=config or {}, created_by=user_id,
            )
            self.session.add(task)
            task_infos.append({"task_id": task_id, "sku_id": sku_id, "config": config or {}})

        await self.session.commit()
        logger.info(f"批次创建完成: {batch_id}, 包含 {len(sku_ids)} 个任务")
        return {"batch_id": batch_id, "tasks": task_infos}

    async def get_batch_detail(self, tenant_id: str, batch_id: str) -> dict:
        b_res = await self.session.execute(
            select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id)
        )
        batch = b_res.scalar_one_or_none()
        if not batch:
            raise ValueError("批次不存在")

        tasks_res = await self.session.execute(select(Task).where(Task.batch_id == batch_id))
        tasks = tasks_res.scalars().all()

        return {
            "batch": {
                "id": batch.id, "name": batch.name, "status": batch.status,
                "total_count": batch.total_count, "completed_count": batch.completed_count,
                "failed_count": batch.failed_count,
            },
            "tasks": [
                {"id": t.id, "sku_id": t.sku_id, "status": t.status, "current_node": t.current_node}
                for t in tasks
            ],
        }
