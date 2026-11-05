"""
AI 模型厂商与 API Key 接入管理接口 (Provider Router)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.models.provider import Provider
from app.clients.provider_factory import ProviderFactory

router = APIRouter(prefix="/providers", tags=["模型厂商管理"])

class ProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_default: Optional[int] = None

@router.get("")
async def list_providers(
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取租户当前配置的模型厂商列表"""
    tenant_id = user_tenant["tenant_id"]
    res = await db.execute(select(Provider).where(Provider.tenant_id == tenant_id, Provider.is_deleted == 0))
    providers = res.scalars().all()

    items = [
        {
            "id": p.id,
            "type": p.type,
            "name": p.name,
            "has_key": bool(p.api_key_enc and p.api_key_enc.strip()),
            "api_key_masked": f"{p.api_key_enc[:4]}****{p.api_key_enc[-4:]}" if p.api_key_enc and len(p.api_key_enc) > 8 else "未配置(使用Mock)",
            "config": p.config,
            "is_default": p.is_default,
        }
        for p in providers
    ]

    return {"code": 200, "data": {"items": items}, "message": "获取成功"}

@router.put("/{provider_id}")
async def update_provider(
    provider_id: str,
    req: ProviderUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """更新模型厂商 API Key 或参数配置"""
    tenant_id = user_tenant["tenant_id"]
    res = await db.execute(select(Provider).where(Provider.id == provider_id, Provider.tenant_id == tenant_id))
    prov = res.scalar_one_or_none()
    if not prov:
        raise HTTPException(status_code=404, detail="厂商配置不存在")

    update_fields = {}
    if req.name is not None:
        update_fields["name"] = req.name
    if req.api_key is not None:
        update_fields["api_key_enc"] = req.api_key.strip()
    if req.config is not None:
        update_fields["config"] = req.config
    if req.is_default is not None:
        update_fields["is_default"] = req.is_default

    if update_fields:
        await db.execute(update(Provider).where(Provider.id == provider_id).values(**update_fields))
        await db.commit()

    return {"code": 200, "data": {"id": provider_id}, "message": "模型厂商配置已保存"}

@router.post("/{provider_id}/test")
async def test_provider_connection(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """在线连通性测试"""
    tenant_id = user_tenant["tenant_id"]
    res = await db.execute(select(Provider).where(Provider.id == provider_id, Provider.tenant_id == tenant_id))
    prov = res.scalar_one_or_none()
    if not prov:
        raise HTTPException(status_code=404, detail="厂商配置不存在")

    if prov.type == "llm":
        client = ProviderFactory.get_llm_client()
        result = await client.chat_completion([{"role": "user", "content": "Hello! 连通性测试"}])
        return {
            "code": 200,
            "data": {"status": "success", "mode": "Mock" if result.get("is_mock") else "Real API", "latency_ms": result.get("elapsed_ms")},
            "message": "LLM 连通性正常"
        }
    elif prov.type == "image":
        client = ProviderFactory.get_image_client()
        result = await client.generate_images("test image")
        return {
            "code": 200,
            "data": {"status": "success", "mode": "Mock" if result.get("is_mock") else "Real API", "latency_ms": result.get("elapsed_ms")},
            "message": "生图服务连通性正常"
        }
    elif prov.type == "video":
        client = ProviderFactory.get_video_client()
        result = await client.generate_video("test video")
        return {
            "code": 200,
            "data": {"status": "success", "mode": "Mock" if result.get("is_mock") else "Real API", "latency_ms": result.get("elapsed_ms")},
            "message": "视频服务连通性正常"
        }
    
    return {"code": 200, "data": {"status": "success"}, "message": "测试通过"}
