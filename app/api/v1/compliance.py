"""
合规质检报告与违禁词检测接口 (Compliance Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant, require_admin
from app.services.compliance_service import ComplianceService
from app.services.delivery_review import decide_delivery, review_copy
from app.services.task_queue import TaskConflictError

router = APIRouter(prefix="/compliance", tags=["合规质检管理"])

class ComplianceCheckRequest(BaseModel):
    title: str
    content: str
    target_platform: Optional[str] = "amazon"


class CopyReviewRequest(BaseModel):
    report_id: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None


class HumanReviewRequest(BaseModel):
    report_id: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    decision: Literal["approved", "rejected"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""


@router.post("/tasks/{task_id}/copy-review")
async def run_copy_review(
    task_id: str,
    req: CopyReviewRequest,
    request_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user_and_tenant),
) -> dict:
    if not request_key.strip():
        raise HTTPException(status_code=422, detail="请求标识不能为空")
    try:
        result = await review_copy(db, user["tenant_id"], task_id, user["user_id"], request_key, req.report_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except TaskConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return {"code": 200, "data": result, "message": "已返回文案审核状态"}


@router.post("/tasks/{task_id}/human-review")
async def submit_human_review(
    task_id: str,
    req: HumanReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> dict:
    if req.decision == "rejected" and not req.note:
        raise HTTPException(status_code=422, detail="请填写驳回原因")
    try:
        result = await decide_delivery(db, user["tenant_id"], task_id, user["user_id"], req.report_id, req.decision, req.note)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except TaskConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return {"code": 200, "data": result, "message": "人工审核结论已保存"}


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
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """一键实时合规筛查接口 (检测广告法、绝对化词汇、侵权违禁词)"""
    from app.services.provider_runtime import provider_scope
    async with provider_scope(user_tenant["tenant_id"], db, kinds=("llm",)):
        result = await ComplianceService.run_realtime_check(req.title, req.content, req.target_platform)
    return {"code": 200, "data": result, "message": "合规检测完毕"}
