"""
批次任务管理接口 (Batch Router)
薄路由层: 仅负责参数解析、权限检查、后台任务调度与 HTTP 响应映射
"""

from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.task_config import TaskConfig
from app.core.deps import get_current_user_and_tenant, get_db
from app.services.batch_service import BatchService
from app.services.task_queue import TaskConflictError

router = APIRouter(prefix="/batches", tags=["批次生成管理"])

class BatchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    sku_ids: List[str] = Field(min_length=1, max_length=100)
    config: TaskConfig = Field(default_factory=TaskConfig)


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
    request_key: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """创建批次并批量生成商品任务"""
    svc = BatchService(db)
    try:
        result = await svc.create_batch(
            tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
            name=req.name, sku_ids=req.sku_ids, config=req.config.model_dump(), request_key=request_key,
        )
    except TaskConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"code": 200, "data": {"batch_id": result["batch_id"], "total_tasks": len(result["tasks"])}, "message": "批次任务已保存并加入执行队列"}


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
    except TaskConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}
