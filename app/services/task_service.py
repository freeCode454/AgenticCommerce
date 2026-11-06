"""
生成任务服务层 (TaskService)
核心业务: 任务的创建、查询、工作流调度、详情聚合
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.models.asset import Asset
from app.models.base import generate_uuid32
from app.models.batch import Batch
from app.models.compliance import ComplianceReport
from app.models.copy import Copy
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_execution import TaskExecution
from app.models.task_node_run import TaskNodeRun
from app.services.base import BaseService
from app.services.task_queue import (
    TaskConflictError,
    deduplicate,
    enqueue,
    refresh_batch,
)

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
            sku_res = await self.session.execute(select(Sku.name, Sku.code).where(Sku.id == t.sku_id, Sku.tenant_id == tenant_id, Sku.is_deleted == 0))
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
        request_key: str | None = None,
    ) -> dict:
        """原子保存任务与排队记录；重复请求复用已有任务"""
        existing, fingerprint = await deduplicate(self.session, Task, tenant_id, request_key, {
            "sku_id": sku_id, "batch_id": batch_id, "config": config or {},
        })
        if existing:
            return {"task_id": existing.id, "sku_id": existing.sku_id, "config": existing.config, "status": existing.status}
        sku_check = await self.session.execute(
            select(Sku).where(Sku.id == sku_id, Sku.tenant_id == tenant_id, Sku.is_deleted == 0)
        )
        if not sku_check.scalar_one_or_none():
            raise ValueError("目标商品 SKU 不存在")
        if batch_id and (await self.session.execute(select(Batch).where(
            Batch.id == batch_id, Batch.tenant_id == tenant_id, Batch.is_deleted == 0,
        ))).scalar_one_or_none() is None:
            raise ValueError("目标批次不存在")

        task_id = generate_uuid32()
        task = Task(
            id=task_id, tenant_id=tenant_id, sku_id=sku_id,
            batch_id=batch_id, request_key=request_key, request_hash=fingerprint,
            retry_count=0, config=config or {}, created_by=user_id,
        )
        self.session.add(task)
        enqueue(self.session, task, user_id)
        await refresh_batch(self.session, tenant_id, batch_id)
        await self.session.commit()

        logger.info(f"任务创建成功: {task_id}, sku={sku_id}")
        return {"task_id": task_id, "sku_id": sku_id, "config": config or {}, "status": "pending"}

    async def get_task_detail(self, tenant_id: str, task_id: str) -> dict:
        """聚合查询: 任务 + 文案 + 素材资产 + 质检报告"""
        res = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0)
        )
        task = res.scalar_one_or_none()
        if not task:
            raise ValueError("任务不存在")

        # 关联查询：仅展示当前执行的产物，历史费用与记录仍保留。
        copy_obj = (await self.session.execute(select(Copy).where(Copy.task_id == task_id, Copy.tenant_id == tenant_id, Copy.is_deleted == 0, Copy.execution_id == task.execution_id).order_by(Copy.create_time.desc(), Copy.id.desc()).limit(1))).scalar_one_or_none()
        assets = (await self.session.execute(select(Asset).where(Asset.task_id == task_id, Asset.tenant_id == tenant_id, Asset.is_deleted == 0, Asset.execution_id == task.execution_id))).scalars().all()
        report_obj = (await self.session.execute(select(ComplianceReport).where(ComplianceReport.task_id == task_id, ComplianceReport.tenant_id == tenant_id, ComplianceReport.is_deleted == 0, ComplianceReport.execution_id == task.execution_id).order_by(ComplianceReport.create_time.desc(), ComplianceReport.id.desc()).limit(1))).scalar_one_or_none()
        sku_obj = (await self.session.execute(select(Sku).where(Sku.id == task.sku_id, Sku.tenant_id == tenant_id, Sku.is_deleted == 0))).scalar_one_or_none()

        return {
            "task": {
                "id": task.id, "sku_id": task.sku_id,
                "sku_name": sku_obj.name if sku_obj else "",
                "sku_code": sku_obj.code if sku_obj else "",
                "status": task.status, "current_node": task.current_node,
                "execution_id": task.execution_id, "error_message": task.error_message,
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
        task = (await self.session.execute(select(Task).where(
            Task.id == task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0,
        ))).scalar_one_or_none()
        if task is None:
            return []
        query = (
            select(TaskNodeRun)
            .where(TaskNodeRun.task_id == task_id, TaskNodeRun.tenant_id == tenant_id, TaskNodeRun.is_deleted == 0, TaskNodeRun.execution_id == task.execution_id)
            .order_by(TaskNodeRun.create_time.asc())
        )
        result = await self.session.execute(query)
        return [
            {
                "id": r.id, "node_name": r.node_name, "status": r.status,
                "execution_id": r.execution_id,
                "elapsed_ms": r.elapsed_ms, "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens, "cost": r.cost,
                "input_data": r.input_data, "output_data": r.output_data,
                "create_time": r.create_time.isoformat() if r.create_time else None,
            }
            for r in result.scalars().all()
        ]

    async def retrigger_task(self, tenant_id: str, task_id: str, request_key: str | None = None) -> dict:
        """锁定任务后创建新的持久化执行，阻止重复排队"""
        res = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0).with_for_update()
        )
        task = res.scalar_one_or_none()
        if not task:
            raise ValueError("任务不存在")
        if request_key is not None:
            if not request_key.strip() or len(request_key) > 128:
                raise TaskConflictError("Idempotency-Key 必须为 1–128 个字符")
            previous = (await self.session.execute(select(TaskExecution.id).where(
                TaskExecution.task_id == task_id, TaskExecution.tenant_id == tenant_id,
                TaskExecution.request_key == request_key, TaskExecution.is_deleted == 0,
            ))).first()
            if previous:
                return {"task_id": task.id, "sku_id": task.sku_id, "config": task.config or {}, "status": task.status}
        active = (await self.session.execute(select(TaskExecution.id).where(
            TaskExecution.task_id == task_id, TaskExecution.tenant_id == tenant_id,
            TaskExecution.status.in_(("pending", "running")), TaskExecution.is_deleted == 0,
        ))).first()
        if task.status in {"pending", "running", "retrying"} or active:
            raise TaskConflictError("任务已排队或正在执行，请勿重复触发")

        enqueue(self.session, task, request_key=request_key)
        await refresh_batch(self.session, tenant_id, task.batch_id)
        await self.session.commit()
        return {"task_id": task_id, "sku_id": task.sku_id, "config": task.config or {}, "status": "pending"}
