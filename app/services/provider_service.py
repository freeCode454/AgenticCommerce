"""Provider configuration writes and sanitized admin views."""

from typing import Any

from sqlalchemy import select, update

from app.conf.config import settings
from app.core.provider_keys import (
    PREFIX,
    ProviderConfigurationError,
    decrypt_api_key,
    encrypt_api_key,
)
from app.models.base import generate_uuid32
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.services.base import BaseService
from app.services.provider_runtime import (
    applied,
    default_config,
    model_config,
    resolve_binding,
)


class ProviderConflictError(ValueError):
    """An existing configuration already uses this name."""


class ProviderService(BaseService):
    async def get(self, tenant_id: str, provider_id: str) -> Provider:
        result = await self.session.execute(
            select(Provider).where(
                Provider.id == provider_id,
                Provider.tenant_id == tenant_id,
                Provider.is_deleted == 0,
            )
        )
        provider = result.scalar_one_or_none()
        if provider is None:
            raise LookupError("厂商配置不存在")
        return provider

    async def list(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = list(
            (
                await self.session.execute(
                    select(Provider)
                    .where(Provider.tenant_id == tenant_id, Provider.is_deleted == 0)
                    .order_by(Provider.type, Provider.id)
                )
            )
            .scalars()
            .all()
        )
        return [self.describe(row) for row in rows]

    @staticmethod
    def describe(provider: Provider) -> dict[str, Any]:
        key_status = "empty"
        if provider.api_key_enc:
            key_status = "legacy"
            if provider.api_key_enc.startswith(PREFIX):
                try:
                    decrypt_api_key(
                        provider.api_key_enc,
                        provider.tenant_id,
                        provider.id,
                        settings.PROVIDER_ENCRYPTION_KEY,
                    )
                    key_status = "encrypted"
                except ProviderConfigurationError:
                    key_status = "unavailable"
        status, has_runtime_key = "pending", False
        effective: dict[str, Any] = {}
        try:
            effective = (
                model_config(provider.type, provider.config)
                if applied(provider)
                else default_config(provider.type)
            )
            if applied(provider):
                binding = resolve_binding(provider)
                has_runtime_key = bool(binding.api_key)
                status = "ready" if has_runtime_key else "missing_key"
        except ProviderConfigurationError:
            status = "invalid_config"
        return {
            "id": provider.id,
            "type": provider.type,
            "name": provider.name,
            "has_key": bool(provider.api_key_enc),
            "api_key_masked": "••••••••" if provider.api_key_enc else "未保存密钥",
            # Never return arbitrary legacy JSON: it may contain credentials in unsupported fields.
            "config": effective,
            "effective_config": effective,
            "is_default": provider.is_default,
            "configuration_status": "applied" if applied(provider) else "pending",
            "is_active": bool(provider.is_default and applied(provider)),
            "runtime_status": status,
            "runtime_has_key": has_runtime_key,
            "key_status": key_status,
            "adapter": "硅基流动 · 文本与向量" if effective.get("service") == "siliconflow" else {
                "llm": "DashScope 语言模型",
                "image": "DashScope Qwen Image",
                "video": "DashScope Wan 视频",
            }.get(provider.type, "未支持"),
        }

    async def _lock_tenant(self, tenant_id: str) -> None:
        # Serialize creation and default selection within the workspace.
        await self.session.execute(
            select(Tenant.id)
            .where(Tenant.id == tenant_id, Tenant.is_deleted == 0)
            .with_for_update()
        )

    async def _check_name(self, tenant_id: str, kind: str, name: str) -> None:
        existing = await self.session.scalar(select(Provider.id).where(
            Provider.tenant_id == tenant_id, Provider.type == kind,
            Provider.name == name, Provider.is_deleted == 0,
        ).limit(1))
        if existing:
            raise ProviderConflictError("此类型已有同名配置，请更换配置名称或刷新列表。")

    async def _clear_default(self, tenant_id: str, kind: str, provider_id: str) -> None:
        await self.session.execute(update(Provider).where(
            Provider.tenant_id == tenant_id, Provider.type == kind,
            Provider.id != provider_id, Provider.is_deleted == 0, Provider.is_default == 1,
        ).values(is_default=0))

    async def create(
        self, tenant_id: str, user_id: str, kind: str, name: str,
        config: dict[str, Any], api_key: str, is_default: int,
    ) -> str:
        config = model_config(kind, config)
        api_key = api_key.strip()
        if config["credential_source"] == "stored" and not api_key:
            raise ProviderConfigurationError("请填写当前工作空间的 API Key。")
        if config["credential_source"] == "environment" and api_key:
            raise ProviderConfigurationError("使用服务端凭据时，请清空 API Key 输入框。")
        provider_id = generate_uuid32()
        provider = Provider(
            id=provider_id, tenant_id=tenant_id, type=kind, name=name, config=config,
            api_key_enc=encrypt_api_key(api_key, tenant_id, provider_id, settings.PROVIDER_ENCRYPTION_KEY),
            is_default=is_default, created_by=user_id,
        )
        if is_default and not resolve_binding(provider).api_key:
            raise ProviderConfigurationError("设为默认前，请配置可用的 API Key。")
        await self._lock_tenant(tenant_id)
        await self._check_name(tenant_id, kind, name)
        if is_default:
            await self._clear_default(tenant_id, kind, provider_id)
        self.session.add(provider)
        await self.session.commit()
        return provider_id

    async def save(
        self, tenant_id: str, provider_id: str, changes: dict[str, Any]
    ) -> None:
        await self._lock_tenant(tenant_id)
        provider = await self.get(tenant_id, provider_id)
        changes = {key: value for key, value in changes.items() if value is not None}
        if not changes:
            return
        config = dict(
            changes.get("config")
            or (provider.config if applied(provider) else default_config(provider.type))
        )
        service = (provider.config or {}).get("service", "dashscope") if applied(provider) else "dashscope"
        if config.setdefault("service", service) != service:
            raise ProviderConfigurationError("更换服务商时，请添加一条新的模型配置。")
        if "credential_source" not in config:
            config["credential_source"] = (
                "stored"
                if changes.get("api_key") or provider.api_key_enc
                else "environment"
            )
        if "api_key" in changes and "config" not in changes and changes["api_key"]:
            config["credential_source"] = "stored"
        config = model_config(provider.type, config)
        ciphertext = provider.api_key_enc
        if "api_key" in changes:
            ciphertext = encrypt_api_key(
                changes["api_key"].strip(),
                tenant_id,
                provider_id,
                settings.PROVIDER_ENCRYPTION_KEY,
            )
        elif ciphertext and not ciphertext.startswith(PREFIX):
            ciphertext = encrypt_api_key(
                ciphertext, tenant_id, provider_id, settings.PROVIDER_ENCRYPTION_KEY
            )
        if config["credential_source"] == "stored":
            decrypt_api_key(
                ciphertext, tenant_id, provider_id, settings.PROVIDER_ENCRYPTION_KEY
            )
        default = changes.get("is_default", provider.is_default)
        name = changes.get("name", provider.name)
        if name != provider.name:
            await self._check_name(tenant_id, provider.type, name)
        if default:
            await self._clear_default(tenant_id, provider.type, provider_id)
        await self.session.execute(
            update(Provider)
            .where(
                Provider.id == provider_id,
                Provider.tenant_id == tenant_id,
                Provider.is_deleted == 0,
            )
            .values(
                name=name,
                config=config,
                api_key_enc=ciphertext,
                is_default=default,
            )
        )
        await self.session.commit()
