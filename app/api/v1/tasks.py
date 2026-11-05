"""
生成任务与智能体工作流执行调度接口 (Task Router)
薄路由层: 仅负责参数解析、权限检查、后台任务调度与 HTTP 响应映射
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.sku import Sku
from app.services.task_service import TaskService

logger = logging.getLogger("tasks_api")
router = APIRouter(prefix="/tasks", tags=["生成任务调度"])

class TaskCreateRequest(BaseModel):
    sku_id: str
    batch_id: Optional[str] = None
    config: Dict[str, Any] = {
        "language": "en",
        "platform": "amazon",
        "model_llm": "qwen",
        "model_image": "wanx",
        "model_video": "kling",
        "max_retries": 2
    }


async def run_agent_workflow_background(task_id: str, tenant_id: str, sku_id: str, config: dict):
    """后台异步触发 7-Agent 工作流（保留在路由层, 因为依赖 BackgroundTasks 生命周期）"""
    try:
        from app.agent.graph import app_workflow
        from app.clients.postgres import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            sku_res = await session.execute(select(Sku).where(Sku.id == sku_id))
            sku = sku_res.scalar_one_or_none()
            if not sku:
                logger.error(f"后台工作流执行失败: 找不到 SKU {sku_id}")
                return
            sku_data = {
                "id": sku.id, "code": sku.code, "name": sku.name,
                "category": sku.category, "specs": sku.specs,
                "description": sku.description, "images": sku.images,
            }

        initial_state = {
            "task_id": task_id, "tenant_id": tenant_id, "sku_id": sku_id,
            "sku_data": sku_data, "config": config,
            "retry_count": 0, "max_retries": config.get("max_retries", 2),
            "completed_steps": [],
        }

        logger.info(f"后台异步启动任务: {task_id}")
        await app_workflow.ainvoke(initial_state)
        logger.info(f"后台任务 {task_id} 顺利执行完成")
    except Exception as e:
        logger.error(f"后台任务 {task_id} 执行遇到严重异常: {str(e)}")


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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """新建生成任务并自动调度 7-Agent 工作流"""
    svc = TaskService(db)
    try:
        result = await svc.create_task(
            tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
            sku_id=req.sku_id, batch_id=req.batch_id, config=req.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 提交至后台执行
    background_tasks.add_task(
        run_agent_workflow_background,
        task_id=result["task_id"], tenant_id=user_tenant["tenant_id"],
        sku_id=req.sku_id, config=req.config,
    )
    return {"code": 200, "data": {"task_id": result["task_id"], "status": "running", "message": "工作流已成功调度执行"}, "message": "任务创建成功"}


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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """手动重新触发任务执行"""
    svc = TaskService(db)
    try:
        result = await svc.retrigger_task(user_tenant["tenant_id"], task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    background_tasks.add_task(
        run_agent_workflow_background,
        task_id=result["task_id"], tenant_id=user_tenant["tenant_id"],
        sku_id=result["sku_id"], config=result["config"],
    )
    return {"code": 200, "data": {"task_id": result["task_id"], "status": "running"}, "message": "重新调度成功"}
