"""
生成任务与智能体工作流执行调度接口 (Task Router)
薄路由层: 仅负责参数解析、权限检查、后台任务调度与 HTTP 响应映射
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.task_config import TaskConfig
from app.core.deps import get_current_user_and_tenant, get_db
from app.services.task_queue import TaskConflictError
from app.services.task_service import TaskService

logger = logging.getLogger("tasks_api")
router = APIRouter(prefix="/tasks", tags=["生成任务调度"])

class TaskCreateRequest(BaseModel):
    sku_id: str
    batch_id: Optional[str] = None
    config: TaskConfig = Field(default_factory=TaskConfig)


@router.get("")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    sku_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页查询生成任务列表"""
    svc = TaskService(db)
    items, total = await svc.list_tasks(user_tenant["tenant_id"], page, page_size, status, sku_id)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.post("")
async def create_task(
    req: TaskCreateRequest,
    request_key: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """新建生成任务并自动调度 7-Agent 工作流"""
    svc = TaskService(db)
    try:
        result = await svc.create_task(
            tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
            sku_id=req.sku_id, batch_id=req.batch_id, config=req.config.model_dump(), request_key=request_key,
        )
    except TaskConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"code": 200, "data": {"task_id": result["task_id"], "status": result["status"], "message": "任务已持久化保存"}, "message": "任务已加入执行队列"}


@router.get("/{task_id}")
async def get_task_detail(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取单个任务详情（含文案产出、素材资产与质检报告）"""
    svc = TaskService(db)
    try:
        result = await svc.get_task_detail(user_tenant["tenant_id"], task_id)
    except TaskConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}


@router.get("/{task_id}/nodes")
async def get_task_node_runs(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取任务节点执行明细列表 (供工作台 DAG 实时渲染)"""
    svc = TaskService(db)
    items = await svc.get_node_runs(user_tenant["tenant_id"], task_id)
    return {"code": 200, "data": {"items": items, "count": len(items)}, "message": "获取成功"}


@router.post("/{task_id}/run")
async def trigger_task_run(
    task_id: str,
    request_key: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """手动重新触发任务执行"""
    svc = TaskService(db)
    try:
        result = await svc.retrigger_task(user_tenant["tenant_id"], task_id, request_key=request_key)
    except TaskConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"code": 200, "data": {"task_id": result["task_id"], "status": result["status"]}, "message": "已加入执行队列"}
