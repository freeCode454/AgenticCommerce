"""Copy-only machine review and administrator decisions for delivery."""

import asyncio
import json
import time

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.generation import CopyDraft
from app.models.base import utc_now
from app.models.compliance import ComplianceReport
from app.models.sku import Sku
from app.models.task import Task
from app.models.task_node_run import TaskNodeRun
from app.services.compliance_service import ComplianceService
from app.services.delivery_content import (
    complete_media, current_media, latest_copy, latest_report, report_data, report_status,
)
from app.services.provider_runtime import provider_scope
from app.services.task_queue import TaskConflictError, refresh_batch

REVIEW_TIMEOUT = 75


async def lock_task(db: AsyncSession, tenant_id: str, task_id: str) -> Task:
    task = (await db.execute(select(Task).where(
        Task.id == task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0,
    ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if task is None:
        raise LookupError("任务不存在")
    return task


async def decide_delivery(
    db: AsyncSession, tenant_id: str, task_id: str, user_id: str, report_id: str,
    decision: str, note: str,
) -> dict:
    task = await lock_task(db, tenant_id, task_id)
    report = await latest_report(db, task)
    if (
        task.status != "completed" or report is None or report.id != report_id
        or report.status != "passed" or report.passed != 1
    ):
        raise TaskConflictError("审核版本已更新或尚未通过机器审核，请刷新工作台")
    if report.human_decision:
        if report.human_decision == decision and report.human_note == (note or None):
            return report_data(report)
        raise TaskConflictError("此版本已有人工结论，请刷新工作台")
    if decision == "approved" and (
        await latest_copy(db, task) is None or not complete_media(task, await current_media(db, task))
    ):
        raise TaskConflictError("当前任务缺少可确认的文案或同轮真实素材")
    report.human_decision = decision
    report.human_note = note or None
    report.human_reviewer_id = user_id
    report.human_reviewed_at = utc_now()
    await db.commit()
    return report_data(report)


async def review_copy(
    db: AsyncSession, tenant_id: str, task_id: str, user_id: str, request_key: str,
    expected_report_id: str | None,
) -> dict:
    task = await lock_task(db, tenant_id, task_id)
    previous = (await db.execute(select(ComplianceReport).where(
        ComplianceReport.tenant_id == tenant_id, ComplianceReport.task_id == task_id,
        ComplianceReport.request_key == request_key, ComplianceReport.is_deleted == 0,
    ))).scalar_one_or_none()
    if previous is not None:
        return report_data(previous)
    if task.status != "review_required":
        raise TaskConflictError("当前任务没有待重新审核的文案")
    prior_report = await latest_report(db, task)
    if (prior_report.id if prior_report else None) != expected_report_id:
        raise TaskConflictError("文案审核状态已更新，请刷新工作台后确认")
    if prior_report and report_status(prior_report) == "reviewing":
        raise TaskConflictError("文案审核正在进行，请稍后刷新工作台")
    copy = await latest_copy(db, task)
    if copy is None or not complete_media(task, await current_media(db, task)):
        raise TaskConflictError("当前任务缺少可复用的同轮真实素材或文案")
    try:
        draft = CopyDraft.model_validate({
            "title": copy.title, "bullets": copy.bullets,
            "description": copy.description, "keywords": copy.keywords,
        })
    except ValidationError:
        raise TaskConflictError("请先补齐标题、五条卖点、描述和 5–8 个关键词，再重审文案") from None
    sku = (await db.execute(select(Sku).where(
        Sku.tenant_id == tenant_id, Sku.id == task.sku_id, Sku.is_deleted == 0,
    ))).scalar_one_or_none()
    if sku is None:
        raise TaskConflictError("关联商品已不存在，无法核对文案事实")
    facts = {field: getattr(sku, field) for field in ("name", "category", "description", "specs")}
    content = json.dumps(draft.model_dump(exclude={"title"}), ensure_ascii=False)

    if prior_report and prior_report.status == "reviewing":
        prior_report.status = "review_interrupted"
    report = ComplianceReport(
        tenant_id=tenant_id, task_id=task_id, sku_id=task.sku_id, execution_id=task.execution_id,
        request_key=request_key, created_by=user_id, status="reviewing", passed=0, score=0,
    )
    async with provider_scope(tenant_id, db, kinds=("llm",)):
        db.add(report)
        await db.commit()  # Persist the paid request's identity before contacting the model.
        start = time.monotonic()
        try:
            async with asyncio.timeout(REVIEW_TIMEOUT):
                result, usage, available = await ComplianceService.evaluate_copy(draft.title, content, facts=facts)
        except TimeoutError:
            result, usage, available = {
                "score": 0.0, "passed": 0, "dimensions": {},
                "violations": ["审核请求超时，服务端费用可能尚未反馈"],
                "suggestions": ["请先确认费用和状态，再决定是否重新审核"],
            }, {}, False

    task = await lock_task(db, tenant_id, task_id)
    report = (await db.execute(select(ComplianceReport).where(
        ComplianceReport.tenant_id == tenant_id, ComplianceReport.task_id == task_id,
        ComplianceReport.id == report.id,
    ).execution_options(populate_existing=True))).scalar_one()
    current = await latest_report(db, task)
    valid = (
        current is not None and current.id == report.id and report.status == "reviewing"
        and task.status == "review_required"
    )
    if valid:
        for key, value in result.items():
            setattr(report, key, value)
        report.status = ("passed" if report.passed else "rejected") if available else "review_error"
        if report.passed:
            task.status = "completed"
            task.error_message = None
            await refresh_batch(db, tenant_id, task.batch_id)
    elif report.status == "reviewing":
        report.status = "outdated"
    db.add(TaskNodeRun(
        tenant_id=tenant_id, task_id=task_id, execution_id=report.execution_id,
        node_name="copy_review", status="success" if valid and report.passed else "failed",
        elapsed_ms=int((time.monotonic() - start) * 1000),
        prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0),
        cost=usage.get("cost", 0.0), created_by=user_id,
        output_data={"report_id": report.id, "status": report.status},
    ))
    await db.commit()
    return report_data(report)
