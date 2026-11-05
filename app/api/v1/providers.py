"""Admin provider configuration and explicit tests of the selected saved record."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.provider_factory import ProviderFactory
from app.core.deps import get_db, require_admin
from app.core.provider_keys import ProviderConfigurationError
from app.services.provider_runtime import provider_scope
from app.services.provider_service import ProviderService

router = APIRouter(prefix="/providers", tags=["模型厂商管理"])


class ProviderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    api_key: SecretStr | None = None
    config: dict[str, Any] | None = None
    is_default: int | None = Field(default=None, ge=0, le=1, strict=True)


@router.get("")
async def list_providers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_tenant: Annotated[dict, Depends(require_admin)],
) -> dict[str, Any]:
    items = await ProviderService(db).list(user_tenant["tenant_id"])
    return {"code": 200, "data": {"items": items}, "message": "获取成功"}


@router.put("/{provider_id}")
async def update_provider(
    provider_id: str,
    req: ProviderUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_tenant: Annotated[dict, Depends(require_admin)],
) -> dict[str, Any]:
    changes = req.model_dump(exclude_unset=True)
    if req.api_key is not None:
        changes["api_key"] = req.api_key.get_secret_value()
    try:
        await ProviderService(db).save(user_tenant["tenant_id"], provider_id, changes)
    except LookupError:
        raise HTTPException(status_code=404, detail="厂商配置不存在") from None
    return {
        "code": 200,
        "data": {"id": provider_id},
        "message": "模型配置已保存；默认配置用于后续新任务",
    }


@router.post("/{provider_id}/test")
async def test_provider_connection(
    provider_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_tenant: Annotated[dict, Depends(require_admin)],
) -> dict[str, Any]:
    service = ProviderService(db)
    try:
        provider = await service.get(user_tenant["tenant_id"], provider_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="厂商配置不存在") from None
    async with provider_scope(user_tenant["tenant_id"], db, provider_id) as snapshot:
        binding = snapshot.get(provider.type)
        if binding is None or not binding.api_key:
            raise ProviderConfigurationError(
                "这条配置缺少可用凭据，请先保存 API Key 或配置服务端凭据。"
            )
        if provider.type == "llm":
            result = await ProviderFactory.get_llm_client().chat_completion(
                [{"role": "user", "content": "Reply OK for a connection test."}],
                max_tokens=32,
            )
        elif provider.type == "image":
            result = await ProviderFactory.get_image_client().generate_images(
                "A plain ceramic cup on a white background, connection test."
            )
        elif provider.type == "video":
            result = await ProviderFactory.get_video_client().generate_video(
                "A stationary ceramic cup on a white background, connection test."
            )
        else:
            raise ProviderConfigurationError("当前模型类型不支持测试。")
    return {
        "code": 200,
        "data": {
            "status": "success",
            "mode": "Mock" if result.get("is_mock") else "Real API",
            "latency_ms": result.get("elapsed_ms"),
            "provider_id": provider_id,
            "model": result.get("model", binding.model),
        },
        "message": "所选配置测试已返回",
    }
