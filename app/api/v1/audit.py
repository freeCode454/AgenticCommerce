"""
操作审计与成本 Token 统计接口 (Audit Router)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_and_tenant, get_db
from app.models.log import OperationLog
from app.models.provider_job import ProviderJob
from app.models.task_node_run import TaskNodeRun

router = APIRouter(prefix="/audit", tags=["审计与成本大盘"])

@router.get("/logs")
async def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页查询操作审计日志"""
    tenant_id = user_tenant["tenant_id"]
    query = select(OperationLog).where(OperationLog.tenant_id == tenant_id, OperationLog.is_deleted == 0)

    if action:
        query = query.where(OperationLog.action == action)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(OperationLog.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "user_name": l.user_name,
            "action": l.action,
            "target_type": l.target_type,
            "target_id": l.target_id,
            "detail": l.detail,
            "create_time": l.create_time.isoformat() if l.create_time else None,
        }
        for l in logs
    ]

    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}

@router.get("/costs")
async def get_cost_analytics(
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """汇总大模型 Token 消耗、生成费用与智能体执行统计"""
    tenant_id = user_tenant["tenant_id"]
    
    # 汇总计算
    sum_query = select(
        func.sum(TaskNodeRun.prompt_tokens),
        func.sum(TaskNodeRun.completion_tokens),
        func.sum(TaskNodeRun.cost),
        func.count(TaskNodeRun.id),
    ).where(TaskNodeRun.tenant_id == tenant_id)

    res = await db.execute(sum_query)
    p_tokens, c_tokens, total_cost, run_count = res.first()

    p_tokens = p_tokens or 0
    c_tokens = c_tokens or 0
    total_cost = round(float(total_cost or 0.0), 4)
    unreported = (await db.execute(select(func.count()).select_from(ProviderJob).where(
        ProviderJob.tenant_id == tenant_id, ProviderJob.is_deleted == 0,
        or_(ProviderJob.remote_id.is_not(None), ProviderJob.status.in_(("submitting", "submission_unknown"))),
    ))).scalar_one()

    return {
        "code": 200,
        "data": {
            "total_runs": run_count or 0,
            "total_prompt_tokens": p_tokens,
            "total_completion_tokens": c_tokens,
            "total_tokens": p_tokens + c_tokens,
            "total_cost_usd": total_cost,
            "unreported_video_jobs": unreported,
            "breakdown_by_model": [],
        },
        "message": "获取成功"
    }
