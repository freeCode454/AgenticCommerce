"""Admin provider configuration and explicit tests of the selected saved record."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.provider_factory import ProviderFactory
from app.core.deps import get_db, require_admin
from app.core.provider_context import ProviderKind
from app.core.provider_keys import ProviderConfigurationError
from app.services.provider_runtime import provider_scope
from app.services.provider_service import ProviderConflictError, ProviderService

router = APIRouter(prefix="/providers", tags=["模型厂商管理"])
ProviderName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class ProviderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    name: ProviderName | None = None
    api_key: SecretStr | None = None
    config: dict[str, Any] | None = None
    is_default: int | None = Field(default=None, ge=0, le=1, strict=True)


class ProviderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    type: ProviderKind
    name: ProviderName
    config: dict[str, Any]
    api_key: SecretStr | None = None
    is_default: int = Field(default=0, ge=0, le=1, strict=True)


@router.get("")
async def list_providers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_tenant: Annotated[dict, Depends(require_admin)],
) -> dict[str, Any]:
    items = await ProviderService(db).list(user_tenant["tenant_id"])
    return {"code": 200, "data": {"items": items}, "message": "获取成功"}


@router.post("")
async def create_provider(
    req: ProviderCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_tenant: Annotated[dict, Depends(require_admin)],
) -> dict[str, Any]:
    try:
        provider_id = await ProviderService(db).create(
            user_tenant["tenant_id"], user_tenant["user_id"], req.type, req.name,
            req.config, req.api_key.get_secret_value() if req.api_key is not None else "", req.is_default,
        )
    except ProviderConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return {"code": 200, "data": {"id": provider_id}, "message": "模型配置已添加"}


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
    except ProviderConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
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
        extra: dict[str, Any] = {}
        if provider.type == "llm":
            client = ProviderFactory.get_llm_client()
            result = await client.chat_completion(
                [{"role": "user", "content": "Reply OK for a connection test."}],
                max_tokens=32,
            )
            if binding.service == "siliconflow":
                vector = await client.get_embedding("A ceramic cup.")
                extra = {"embedding_model": binding.embedding_model, "embedding_dimensions": len(vector)}
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
            **extra,
        },
        "message": "所选配置测试已返回",
    }
