"""
合规质检报告与违禁词检测接口 (Compliance Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["合规质检管理"])

class ComplianceCheckRequest(BaseModel):
    title: str
    content: str
    target_platform: Optional[str] = "amazon"


@router.get("/reports")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    task_id: Optional[str] = None,
    sku_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页获取合规质检报告"""
    svc = ComplianceService(db)
    items, total = await svc.list_reports(user_tenant["tenant_id"], page, page_size, task_id, sku_id)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.get("/reports/{report_id}")
async def get_report_detail(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取单个合规质检报告详情"""
    svc = ComplianceService(db)
    try:
        result = await svc.get_report(user_tenant["tenant_id"], report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}


@router.post("/check")
async def run_compliance_check(
    req: ComplianceCheckRequest,
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """一键实时合规筛查接口 (检测广告法、绝对化词汇、侵权违禁词)"""
    result = await ComplianceService.run_realtime_check(req.title, req.content, req.target_platform)
    return {"code": 200, "data": result, "message": "合规检测完毕"}
