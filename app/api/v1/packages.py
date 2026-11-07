"""
交付物打包与下载接口 (Packages Router)
"""

import json
from tempfile import TemporaryFile
from typing import BinaryIO
from zipfile import ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.task import Task
from app.models.sku import Sku
from app.models.asset import Asset
from app.services.delivery_content import complete_media, current_media, human_review, latest_copy, latest_report
from app.services.media_archive import CHUNK_SIZE, MEDIA_EXTENSIONS, archive_metadata_valid, iter_object

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
        sku_res = await db.execute(select(Sku.name, Sku.code).where(Sku.id == t.sku_id, Sku.tenant_id == tenant_id, Sku.is_deleted == 0))
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

async def load_delivery(
    db: AsyncSession, tenant_id: str, task_id: str, *, lock: bool = False,
) -> tuple[Task, list[Asset], dict]:
    task_query = select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0)
    task = (await db.execute(task_query.with_for_update(read=True) if lock else task_query)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="任务尚未完成或需要重新审核")

    report_obj = await latest_report(db, task)
    if report_obj is None or report_obj.passed != 1 or report_obj.status != "passed":
        raise HTTPException(status_code=409, detail="交付前必须通过最新审核")

    copy_obj = await latest_copy(db, task)
    assets = await current_media(db, task)
    if copy_obj is None or not assets or any(a.is_mock for a in assets):
        raise HTTPException(status_code=409, detail="缺少真实交付物")

    return task, assets, {
        "task_id": task.id,
        "sku_id": task.sku_id,
        "copywriting": {
            "title": copy_obj.title,
            "bullets": copy_obj.bullets,
            "description": copy_obj.description,
            "keywords": copy_obj.keywords,
        },
        "media_assets": [
            {"type": a.type, "sub_type": a.sub_type, "url": a.display_url, "archive_status": a.archive_status}
            for a in assets
        ],
        "quality_audit": {
            "score": report_obj.score,
            "passed": report_obj.passed,
            "suggestions": report_obj.suggestions,
            "human_review": human_review(report_obj),
        },
    }


def download_block_reason(task: Task, assets: list[Asset], decision: str) -> str | None:
    if decision == "rejected":
        return "人工审核已驳回，请在工作台查看原因。"
    if decision != "approved":
        return "待管理员人工审核通过后开放下载。"
    if not complete_media(task, assets):
        return "无法确认本次审核对应的完整媒体，暂不能打包。"
    if any(asset.archive_status == "failed" for asset in assets):
        return "有媒体归档失败，请在素材库查看原因。"
    if any(not asset.archive_key for asset in assets):
        return "媒体正在归档，稍后刷新清单即可下载。"
    if any(not archive_metadata_valid(
        asset.archive_size or 0, asset.archive_content_type or "", asset.type,
    ) for asset in assets):
        return "归档媒体暂不可用，请联系管理员。"
    return None


@router.post("/export")
async def export_package(
    req: PackageExportRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
) -> dict:
    task, assets, manifest = await load_delivery(db, user_tenant["tenant_id"], req.task_id)
    reason = download_block_reason(task, assets, manifest["quality_audit"]["human_review"]["decision"])
    return {
        "code": 200,
        "data": {
            **manifest,
            "download_archive_url": None if reason else f"/api/v1/packages/{task.id}/download",
            "download_block_reason": reason,
        },
        "message": "交付清单已生成",
    }


def write_zip(file: BinaryIO, assets: list[Asset], manifest: dict) -> int:
    with ZipFile(file, "w") as archive:
        archive.writestr("copy.json", json.dumps(manifest["copywriting"], ensure_ascii=False, indent=2))
        archive.writestr("review.json", json.dumps(manifest["quality_audit"], ensure_ascii=False, indent=2))
        for asset in assets:
            extension = MEDIA_EXTENSIONS[asset.archive_content_type]
            with archive.open(f"{asset.type}/{asset.sub_type}.{extension}", "w") as output:
                for chunk in iter_object(asset.archive_key, asset.archive_size):
                    output.write(chunk)
    size = file.tell()
    file.seek(0)
    return size


@router.get("/{task_id}/download")
async def download_package(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
) -> StreamingResponse:
    task, assets, manifest = await load_delivery(db, user_tenant["tenant_id"], task_id, lock=True)
    reason = download_block_reason(task, assets, manifest["quality_audit"]["human_review"]["decision"])
    if reason:
        raise HTTPException(status_code=409, detail=reason)

    file = TemporaryFile()
    try:
        size = await run_in_threadpool(write_zip, file, assets, manifest)
        # Release the task lock before sending the file to the browser.
        await db.commit()
    except BaseException as exc:
        file.close()
        if not isinstance(exc, Exception):
            raise
        raise HTTPException(status_code=503, detail="交付文件暂时无法打包，请稍后重试") from None

    return StreamingResponse(
        iter(lambda: file.read(CHUNK_SIZE), b""), media_type="application/zip",
        background=BackgroundTask(file.close),
        headers={
            "Content-Length": str(size), "Cache-Control": "private, no-store",
            "Content-Disposition": 'attachment; filename="delivery.zip"',
            "X-Content-Type-Options": "nosniff",
        },
    )
