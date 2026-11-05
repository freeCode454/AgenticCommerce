"""
交付物打包与下载接口 (Packages Router)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.task import Task
from app.models.sku import Sku
from app.models.copy import Copy
from app.models.asset import Asset
from app.models.compliance import ComplianceReport

router = APIRouter(prefix="/packages", tags=["交付打包下载"])

class PackageExportRequest(BaseModel):
    task_id: str

@router.get("")
async def list_packages(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取所有已完成并可打包交付的任务列表"""
    tenant_id = user_tenant["tenant_id"]
    query = (
        select(Task)
        .where(Task.tenant_id == tenant_id, Task.status == "completed", Task.is_deleted == 0)
        .order_by(Task.update_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        sku_res = await db.execute(select(Sku.name, Sku.code).where(Sku.id == t.sku_id))
        sku_info = sku_res.first()
        items.append({
            "task_id": t.id,
            "sku_id": t.sku_id,
            "sku_name": sku_info[0] if sku_info else "",
            "sku_code": sku_info[1] if sku_info else "",
            "package_name": f"Delivery_{sku_info[1] if sku_info else t.id}.zip",
            "status": "ready",
            "create_time": t.update_time.isoformat() if t.update_time else None,
        })

    return {
        "code": 200,
        "data": {"items": items, "count": len(items)},
        "message": "获取成功"
    }

@router.post("/export")
async def export_package(
    req: PackageExportRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """导出并打包任务全量交付物 (文案 JSON + 图像资产清单 + 视频 + 质检报告)"""
    tenant_id = user_tenant["tenant_id"]
    t_res = await db.execute(select(Task).where(Task.id == req.task_id, Task.tenant_id == tenant_id))
    task = t_res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    copy_res = await db.execute(select(Copy).where(Copy.task_id == req.task_id))
    copy_obj = copy_res.scalar_one_or_none()

    assets_res = await db.execute(select(Asset).where(Asset.task_id == req.task_id))
    assets = assets_res.scalars().all()

    report_res = await db.execute(select(ComplianceReport).where(ComplianceReport.task_id == req.task_id))
    report_obj = report_res.scalar_one_or_none()

    package_content = {
        "task_id": task.id,
        "sku_id": task.sku_id,
        "copywriting": {
            "title": copy_obj.title if copy_obj else "",
            "bullets": copy_obj.bullets if copy_obj else [],
            "description": copy_obj.description if copy_obj else "",
            "keywords": copy_obj.keywords if copy_obj else [],
        },
        "media_assets": [
            {"type": a.type, "sub_type": a.sub_type, "url": a.url}
            for a in assets
        ],
        "quality_audit": {
            "score": report_obj.score if report_obj else 0.0,
            "passed": report_obj.passed if report_obj else 0,
            "suggestions": report_obj.suggestions if report_obj else [],
        },
        "download_archive_url": f"https://mock-storage.agentic.com/packages/{task.id}.zip"
    }

    return {
        "code": 200,
        "data": package_content,
        "message": "交付包打包就绪"
    }
