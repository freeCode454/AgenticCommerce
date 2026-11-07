"""Select the latest copy, review, and same-round media for an execution."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.base import utc_now
from app.models.compliance import ComplianceReport
from app.models.copy import Copy
from app.models.task import Task

DELIVERY_MEDIA = {("image", "main"), ("image", "scene"), ("image", "detail"), ("video", "product_showcase")}
REVIEW_LEASE = timedelta(seconds=120)


def report_status(report: ComplianceReport) -> str:
    if report.status == "reviewing" and utc_now() >= report.create_time + REVIEW_LEASE:
        return "review_interrupted"
    return report.status


def human_review(report: ComplianceReport) -> dict:
    return {
        "decision": report.human_decision or "pending",
        "reviewer_id": report.human_reviewer_id,
        "reviewed_at": report.human_reviewed_at.isoformat() if report.human_reviewed_at else None,
        "note": report.human_note,
    }


def report_data(report: ComplianceReport) -> dict:
    return {
        "id": report.id, "task_id": report.task_id, "sku_id": report.sku_id,
        "score": report.score, "passed": report.passed, "dimensions": report.dimensions,
        "violations": report.violations, "suggestions": report.suggestions,
        "status": report_status(report), "scope": "copy" if report.request_key else "generation",
        "human_review": human_review(report),
        "create_time": report.create_time.isoformat() if report.create_time else None,
    }


async def latest_copy(db: AsyncSession, task: Task) -> Copy | None:
    return (await db.execute(select(Copy).where(
        Copy.task_id == task.id, Copy.tenant_id == task.tenant_id,
        Copy.is_deleted == 0, Copy.execution_id == task.execution_id,
    ).order_by(Copy.create_time.desc(), Copy.id.desc()).limit(1))).scalar_one_or_none()


async def latest_report(db: AsyncSession, task: Task) -> ComplianceReport | None:
    return (await db.execute(select(ComplianceReport).where(
        ComplianceReport.task_id == task.id, ComplianceReport.tenant_id == task.tenant_id,
        ComplianceReport.is_deleted == 0, ComplianceReport.execution_id == task.execution_id,
    ).order_by(ComplianceReport.create_time.desc(), ComplianceReport.id.desc()).limit(1))).scalar_one_or_none()


async def current_media(db: AsyncSession, task: Task) -> list[Asset]:
    assets = list(await db.scalars(select(Asset).where(
        Asset.task_id == task.id, Asset.tenant_id == task.tenant_id,
        Asset.is_deleted == 0, Asset.execution_id == task.execution_id,
    ).order_by(Asset.type, Asset.sub_type, Asset.id)))
    if any(asset.generation_round is not None for asset in assets):
        return [asset for asset in assets if asset.generation_round == task.retry_count]
    return assets


def complete_media(task: Task, assets: list[Asset]) -> bool:
    return (
        bool(task.execution_id) and len(assets) == len(DELIVERY_MEDIA)
        and {(asset.type, asset.sub_type) for asset in assets} == DELIVERY_MEDIA
        and all(asset.status == "completed" and not asset.is_mock and asset.url for asset in assets)
        and (task.retry_count == 0 or all(asset.generation_round is not None for asset in assets))
    )
