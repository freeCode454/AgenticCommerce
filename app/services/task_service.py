"""
生成任务服务层 (TaskService)
核心业务: 任务的创建、查询、工作流调度、详情聚合
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy import select, update
from app.services.base import BaseService
from app.models.task import Task
from app.models.sku import Sku
from app.models.task_node_run import TaskNodeRun
from app.models.copy import Copy
from app.models.asset import Asset
from app.models.compliance import ComplianceReport
from app.models.base import generate_uuid32

logger = logging.getLogger("task_service")


class TaskService(BaseService):

    async def list_tasks(
        self, tenant_id: str, page: int = 1, page_size: int = 10,
        status: Optional[str] = None, sku_id: Optional[str] = None,
    ) -> tuple:
        """分页查询任务列表（含 SKU 关联信息）"""
        query = select(Task).where(Task.tenant_id == tenant_id, Task.is_deleted == 0)
        if status:
            query = query.where(Task.status == status)
        if sku_id:
            query = query.where(Task.sku_id == sku_id)
        query = query.order_by(Task.create_time.desc())

        items, total = await self.paginate(query, page, page_size)

        result = []
        for t in items:
            sku_res = await self.session.execute(select(Sku.name, Sku.code).where(Sku.id == t.sku_id))
            sku_info = sku_res.first()
            result.append({
                "id": t.id, "sku_id": t.sku_id,
                "sku_code": sku_info[1] if sku_info else "",
                "sku_name": sku_info[0] if sku_info else "",
                "batch_id": t.batch_id, "status": t.status,
                "current_node": t.current_node, "retry_count": t.retry_count,
                "config": t.config,
                "create_time": t.create_time.isoformat() if t.create_time else None,
            })
        return result, total

    async def create_task(
        self, tenant_id: str, user_id: str,
        sku_id: str, batch_id: Optional[str] = None,
        config: Dict[str, Any] = None,
    ) -> dict:
        """创建任务记录，验证 SKU 存在性，返回 task_id 供路由层调度工作流"""
        sku_check = await self.session.execute(
            select(Sku).where(Sku.id == sku_id, Sku.tenant_id == tenant_id)
        )
        if not sku_check.scalar_one_or_none():
            raise ValueError("目标商品 SKU 不存在")

        task_id = f"task_{generate_uuid32()[:12]}"
        task = Task(
            id=task_id, tenant_id=tenant_id, sku_id=sku_id,
            batch_id=batch_id, status="running", current_node="orchestrator",
            retry_count=0, config=config or {}, created_by=user_id,
        )
        self.session.add(task)
        await self.session.commit()

        logger.info(f"任务创建成功: {task_id}, sku={sku_id}")
        return {"task_id": task_id, "sku_id": sku_id, "config": config or {}}

    async def get_task_detail(self, tenant_id: str, task_id: str) -> dict:
        """聚合查询: 任务 + 文案 + 素材资产 + 质检报告"""
        res = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
        )
        task = res.scalar_one_or_none()
        if not task:
            raise ValueError("任务不存在")

        # 关联查询
        copy_obj = (await self.session.execute(select(Copy).where(Copy.task_id == task_id))).scalar_one_or_none()
        assets = (await self.session.execute(select(Asset).where(Asset.task_id == task_id))).scalars().all()
        report_obj = (await self.session.execute(select(ComplianceReport).where(ComplianceReport.task_id == task_id))).scalar_one_or_none()
        sku_obj = (await self.session.execute(select(Sku).where(Sku.id == task.sku_id))).scalar_one_or_none()

        return {
            "task": {
                "id": task.id, "sku_id": task.sku_id,
                "sku_name": sku_obj.name if sku_obj else "",
                "sku_code": sku_obj.code if sku_obj else "",
                "status": task.status, "current_node": task.current_node,
                "retry_count": task.retry_count, "config": task.config,
                "create_time": task.create_time.isoformat() if task.create_time else None,
            },
            "copy": {
                "title": copy_obj.title, "bullets": copy_obj.bullets,
                "description": copy_obj.description, "keywords": copy_obj.keywords,
            } if copy_obj else None,
            "assets": [
                {"id": a.id, "type": a.type, "sub_type": a.sub_type, "url": a.url, "is_mock": a.is_mock, "meta": a.meta}
                for a in assets
            ],
            "compliance_report": {
                "score": report_obj.score, "passed": report_obj.passed,
                "dimensions": report_obj.dimensions, "violations": report_obj.violations,
                "suggestions": report_obj.suggestions,
            } if report_obj else None,
        }

    async def get_node_runs(self, tenant_id: str, task_id: str) -> list:
        """获取任务节点执行明细"""
        query = (
            select(TaskNodeRun)
            .where(TaskNodeRun.task_id == task_id, TaskNodeRun.tenant_id == tenant_id)
            .order_by(TaskNodeRun.create_time.asc())
        )
        result = await self.session.execute(query)
        return [
            {
                "id": r.id, "node_name": r.node_name, "status": r.status,
                "elapsed_ms": r.elapsed_ms, "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens, "cost": r.cost,
                "input_data": r.input_data, "output_data": r.output_data,
                "create_time": r.create_time.isoformat() if r.create_time else None,
            }
            for r in result.scalars().all()
        ]

    async def retrigger_task(self, tenant_id: str, task_id: str) -> dict:
        """重新触发任务，返回 task 信息供路由层调度"""
        res = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
        )
        task = res.scalar_one_or_none()
        if not task:
            raise ValueError("任务不存在")

        await self.session.execute(
            update(Task).where(Task.id == task_id).values(status="running", current_node="orchestrator")
        )
        await self.session.commit()
        return {"task_id": task_id, "sku_id": task.sku_id, "config": task.config or {}}
