"""Tenant provider resolution. Loading a snapshot does not call any model."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.postgres import AsyncSessionLocal
from app.conf.config import settings
from app.core.provider_context import (
    ProviderBinding,
    ProviderKind,
    ProviderServiceName,
    ProviderSnapshot,
    active_providers,
)
from app.core.provider_keys import ProviderConfigurationError, decrypt_api_key
from app.models.provider import Provider

DEFAULT_MODELS = {
    "llm": "qwen-plus",
    "image": "qwen-image-3.0-pro",
    "video": "wan3.0-video",
}


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    model: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
    )
    credential_source: Literal["environment", "stored"]
    service: ProviderServiceName = "dashscope"
    embedding_model: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
    )


def model_config(kind: str, value: dict[str, Any]) -> dict[str, Any]:
    if kind not in DEFAULT_MODELS:
        raise ProviderConfigurationError("当前厂商类型没有可用的模型适配器。")
    try:
        parsed = ModelConfig.model_validate(value)
        if kind != "llm" and parsed.embedding_model is not None:
            raise ValueError()
    except (ValidationError, ValueError):
        raise ProviderConfigurationError(
            "模型参数无效，请核对服务商、模型 ID 和凭据来源。"
        ) from None
    if parsed.service == "siliconflow" and (kind != "llm" or parsed.credential_source != "stored"):
        raise ProviderConfigurationError("硅基流动当前支持语言与向量模型，请使用工作空间 API Key。")
    result = parsed.model_dump(exclude_none=True)
    if kind == "llm":
        result.setdefault("embedding_model", "BAAI/bge-m3" if parsed.service == "siliconflow" else "text-embedding-v4")
    return result


def default_config(kind: str) -> dict[str, Any]:
    return model_config(
        kind,
        {"model": DEFAULT_MODELS.get(kind, ""), "credential_source": "environment"},
    )


def applied(provider: Provider) -> bool:
    return isinstance(provider.config, dict) and "credential_source" in provider.config


def resolve_binding(provider: Provider) -> ProviderBinding:
    if not applied(provider):
        raise ProviderConfigurationError("请先保存这条旧配置，再测试或应用。")
    config = model_config(provider.type, provider.config)
    # None is deliberately distinct from an empty stored credential in the clients.
    if config["credential_source"] == "stored":
        key = decrypt_api_key(
            provider.api_key_enc,
            provider.tenant_id,
            provider.id,
            settings.PROVIDER_ENCRYPTION_KEY,
        )
    else:
        key = {
            "llm": settings.DASHSCOPE_API_KEY,
            "image": settings.WANX_API_KEY or settings.DASHSCOPE_API_KEY,
            "video": settings.DASHSCOPE_API_KEY,
        }[provider.type]
    return ProviderBinding(
        provider.id,
        config["model"],
        key,
        config.get("embedding_model", "text-embedding-v4"),
        service=config["service"],
    )


async def load_snapshot(
    db: AsyncSession,
    tenant_id: str,
    provider_id: str | None = None,
    kinds: tuple[ProviderKind, ...] | None = None,
) -> ProviderSnapshot:
    query = select(Provider).where(
        Provider.tenant_id == tenant_id, Provider.is_deleted == 0
    )
    if provider_id is not None:
        query = query.where(Provider.id == provider_id)
    if kinds is not None:
        query = query.where(Provider.type.in_(kinds))
    rows = list((await db.execute(query)).scalars().all())
    if provider_id is not None and (len(rows) != 1 or not applied(rows[0])):
        raise ProviderConfigurationError("目标配置不存在、不可访问或尚未保存应用。")
    bindings: dict[str, ProviderBinding] = {}
    for provider in rows:
        if provider.tenant_id != tenant_id or (
            provider_id is not None and provider.id != provider_id
        ):
            raise ProviderConfigurationError("模型配置不属于当前工作空间或目标记录。")
        if provider_id is None and (not provider.is_default or not applied(provider)):
            continue
        if provider.type in bindings:
            raise ProviderConfigurationError(
                "同一模型类型存在多条默认配置，请由管理员重新选择默认配置。"
            )
        bindings[provider.type] = resolve_binding(provider)
    return ProviderSnapshot(tenant_id, tuple(bindings.items()))


@asynccontextmanager
async def provider_scope(
    tenant_id: str,
    db: AsyncSession | None = None,
    provider_id: str | None = None,
    kinds: tuple[ProviderKind, ...] | None = None,
) -> AsyncIterator[ProviderSnapshot]:
    if db is None:
        async with AsyncSessionLocal() as session:
            snapshot = await load_snapshot(session, tenant_id, provider_id, kinds)
    else:
        snapshot = await load_snapshot(db, tenant_id, provider_id, kinds)
    token = active_providers.set(snapshot)
    try:
        yield snapshot
    finally:
        active_providers.reset(token)
