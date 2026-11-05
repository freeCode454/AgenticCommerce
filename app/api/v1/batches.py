"""
批次任务管理接口 (Batch Router)
薄路由层: 仅负责参数解析、权限检查、后台任务调度与 HTTP 响应映射
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.batch_service import BatchService
from app.api.v1.tasks import run_agent_workflow_background

router = APIRouter(prefix="/batches", tags=["批次生成管理"])

class BatchCreateRequest(BaseModel):
    name: str
    sku_ids: List[str]
    config: Dict[str, Any] = {
        "language": "en",
        "platform": "amazon",
        "model_llm": "qwen",
        "model_image": "wanx",
        "model_video": "kling"
    }


@router.get("")
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页获取批次列表"""
    svc = BatchService(db)
    items, total = await svc.list_batches(user_tenant["tenant_id"], page, page_size)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.post("")
async def create_batch(
    req: BatchCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """创建批次并批量生成商品任务"""
    svc = BatchService(db)
    try:
        result = await svc.create_batch(
            tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
            name=req.name, sku_ids=req.sku_ids, config=req.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 调度所有子任务的后台工作流
    for task_info in result["tasks"]:
        background_tasks.add_task(
            run_agent_workflow_background,
            task_id=task_info["task_id"], tenant_id=user_tenant["tenant_id"],
            sku_id=task_info["sku_id"], config=task_info["config"],
        )

    return {"code": 200, "data": {"batch_id": result["batch_id"], "total_tasks": len(result["tasks"])}, "message": "批次任务创建成功并已启动"}


@router.get("/{batch_id}")
async def get_batch_detail(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取单个批次及下属任务状态"""
    svc = BatchService(db)
    try:
        result = await svc.get_batch_detail(user_tenant["tenant_id"], batch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}
