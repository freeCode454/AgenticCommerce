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
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.services.base import BaseService
from app.services.provider_runtime import (
    applied,
    default_config,
    model_config,
    resolve_binding,
)


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
            effective, status = {}, "invalid_config"
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
            "adapter": {
                "llm": "DashScope 语言模型",
                "image": "DashScope Qwen Image",
                "video": "DashScope Wan 视频",
            }.get(provider.type, "未支持"),
        }

    async def save(
        self, tenant_id: str, provider_id: str, changes: dict[str, Any]
    ) -> None:
        # Lock the tenant row so concurrent default switches commit atomically.
        await self.session.execute(
            select(Tenant.id)
            .where(Tenant.id == tenant_id, Tenant.is_deleted == 0)
            .with_for_update()
        )
        provider = await self.get(tenant_id, provider_id)
        changes = {key: value for key, value in changes.items() if value is not None}
        if not changes:
            return
        config = dict(
            changes.get("config")
            or (provider.config if applied(provider) else default_config(provider.type))
        )
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
        if default:
            await self.session.execute(
                update(Provider)
                .where(
                    Provider.tenant_id == tenant_id,
                    Provider.type == provider.type,
                    Provider.id != provider_id,
                    Provider.is_deleted == 0,
                )
                .values(is_default=0)
            )
        await self.session.execute(
            update(Provider)
            .where(
                Provider.id == provider_id,
                Provider.tenant_id == tenant_id,
                Provider.is_deleted == 0,
            )
            .values(
                name=changes.get("name", provider.name),
                config=config,
                api_key_enc=ciphertext,
                is_default=default,
            )
        )
        await self.session.commit()
