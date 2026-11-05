"""Provider encryption and concurrent tenant binding tests; no real model requests."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.clients.provider_factory import ProviderFactory
from app.conf.config import Settings, settings
from app.core.provider_context import active_providers
from app.core.provider_keys import (
    ProviderConfigurationError,
    decrypt_api_key,
    encrypt_api_key,
    new_encryption_key,
)
from app.models.provider import Provider
from app.services.provider_runtime import model_config, provider_scope


@pytest.fixture
def master(monkeypatch):
    key = new_encryption_key()
    monkeypatch.setattr(settings, "PROVIDER_ENCRYPTION_KEY", key)
    return key


def row(
    master,
    tenant="tenant-a",
    provider="provider-a",
    kind="llm",
    key="offline-test-secret",
    default=1,
):
    return Provider(
        id=provider,
        tenant_id=tenant,
        type=kind,
        name="Offline provider",
        config={"model": "offline-model", "credential_source": "stored"},
        api_key_enc=encrypt_api_key(key, tenant, provider, master),
        is_default=default,
    )


def database(rows):
    result = Mock()
    result.scalars.return_value.all.return_value = rows
    db = AsyncMock()
    db.execute.return_value = result
    return db


def test_ciphertext_is_randomized_bound_and_fits_existing_column(master):
    secret = "test-value-" * 20
    first = encrypt_api_key(secret, "tenant-a", "provider-a", master)
    second = encrypt_api_key(secret, "tenant-a", "provider-a", master)
    assert first != second and secret not in first
    assert len(first) <= 512
    assert decrypt_api_key(first, "tenant-a", "provider-a", master) == secret


@pytest.mark.parametrize(
    "tenant,provider", [("tenant-b", "provider-a"), ("tenant-a", "provider-b")]
)
def test_ciphertext_cannot_move_between_tenants_or_records(master, tenant, provider):
    ciphertext = encrypt_api_key(
        "offline-sensitive-value", "tenant-a", "provider-a", master
    )
    with pytest.raises(ProviderConfigurationError) as error:
        decrypt_api_key(ciphertext, tenant, provider, master)
    assert "offline-sensitive-value" not in str(error.value)


def test_wrong_key_corruption_and_legacy_values_fail_closed(master):
    ciphertext = encrypt_api_key(
        "offline-sensitive-value", "tenant-a", "provider-a", master
    )
    for token, key in [
        (ciphertext, new_encryption_key()),
        (ciphertext[:-6] + "AAAAAA", master),
        ("legacy-plaintext", master),
    ]:
        with pytest.raises(ProviderConfigurationError):
            decrypt_api_key(token, "tenant-a", "provider-a", key)


@pytest.mark.parametrize("secret", ["x" * 257, "secret\nvalue", "secret\x00value"])
def test_unstorable_keys_are_rejected_without_echoing_input(master, secret):
    with pytest.raises(ProviderConfigurationError) as error:
        encrypt_api_key(secret, "tenant-a", "provider-a", master)
    assert secret not in str(error.value)


@pytest.mark.parametrize("value", ["", "bad-key", "MDAwMDAwMDA="])
def test_missing_or_invalid_master_key_prevents_storage(value):
    with pytest.raises(ProviderConfigurationError):
        encrypt_api_key("test-credential", "tenant-a", "provider-a", value)


def test_production_requires_independent_valid_master_key(master):
    safe = {
        "APP_ENV": "prod",
        "DEBUG": False,
        "ALLOW_MOCK_ASSETS": False,
        "AUTH_ENABLED": True,
        "SECRET_KEY": "jwt-test-" * 8,
        "POSTGRES_PASSWORD": "db-test-password",
        "MINIO_SECRET_KEY": "storage-test-password",
        "PROVIDER_ENCRYPTION_KEY": master,
    }
    assert Settings(_env_file=None, **safe).PROVIDER_ENCRYPTION_KEY == master
    for value in ["", "invalid"]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**safe, "PROVIDER_ENCRYPTION_KEY": value})
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**safe, "SECRET_KEY": master})
    assert master not in repr(Settings(_env_file=None, **safe))


async def test_overlapping_tenant_calls_use_isolated_keys_models_and_reset(master):
    gate = asyncio.Event()

    async def resolve(tenant, provider, secret):
        db = database([row(master, tenant, provider, key=secret)])
        async with provider_scope(tenant, db):
            await gate.wait()
            client = ProviderFactory.get_llm_client()
            assert active_providers.get().tenant_id == tenant
            return client.api_key, client.model

    tasks = [
        asyncio.create_task(resolve("tenant-a", "provider-a", "key-a")),
        asyncio.create_task(resolve("tenant-b", "provider-b", "key-b")),
    ]
    gate.set()
    assert await asyncio.gather(*tasks) == [
        ("key-a", "offline-model"),
        ("key-b", "offline-model"),
    ]
    assert active_providers.get() is None


async def test_scope_resets_after_exception_and_nested_test_scope(master):
    with pytest.raises(RuntimeError):
        async with provider_scope("tenant-a", database([row(master)])):
            async with provider_scope(
                "tenant-b",
                database([row(master, "tenant-b", "provider-b", key="key-b")]),
            ):
                assert ProviderFactory.get_llm_client().api_key == "key-b"
            assert ProviderFactory.get_llm_client().api_key == "offline-test-secret"
            raise RuntimeError("Offline error")
    assert active_providers.get() is None


async def test_empty_stored_key_never_uses_server_fallback(master, monkeypatch):
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "server-test-secret")
    async with provider_scope("tenant-a", database([row(master, key="")])):
        assert ProviderFactory.get_llm_client().api_key == ""


async def test_snapshot_survives_later_config_changes_and_new_scope_sees_change(master):
    provider = row(master)
    async with provider_scope("tenant-a", database([provider])):
        provider.config = {"model": "updated-model", "credential_source": "stored"}
        provider.api_key_enc = encrypt_api_key(
            "updated-key", "tenant-a", "provider-a", master
        )
        assert ProviderFactory.get_llm_client().model == "offline-model"
        assert ProviderFactory.get_llm_client().api_key == "offline-test-secret"
    async with provider_scope("tenant-a", database([provider])):
        assert ProviderFactory.get_llm_client().model == "updated-model"
        assert ProviderFactory.get_llm_client().api_key == "updated-key"


async def test_legacy_records_do_not_override_runtime_and_explicit_test_requires_save(
    master, monkeypatch
):
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "server-test-secret")
    provider = row(master)
    provider.config = {"model": "old-draft-model"}
    async with provider_scope("tenant-a", database([provider])):
        assert ProviderFactory.get_llm_client().api_key == "server-test-secret"
        assert ProviderFactory.get_llm_client().model is None
    with pytest.raises(ProviderConfigurationError):
        async with provider_scope(
            "tenant-a", database([provider]), provider_id=provider.id
        ):
            pytest.fail("Unapplied configuration was accepted")


async def test_duplicate_defaults_do_not_choose_arbitrary_key(master):
    with pytest.raises(ProviderConfigurationError):
        async with provider_scope(
            "tenant-a", database([row(master), row(master, provider="provider-other")])
        ):
            pytest.fail("Ambiguous default was accepted")


@pytest.mark.parametrize("kind", ["llm", "image", "video"])
async def test_each_factory_receives_its_selected_binding(master, kind):
    provider = row(master, kind=kind)
    async with provider_scope("tenant-a", database([provider])):
        client = {
            "llm": ProviderFactory.get_llm_client,
            "image": ProviderFactory.get_image_client,
            "video": ProviderFactory.get_video_client,
        }[kind]()
        assert client.api_key == "offline-test-secret"
        assert client.model == "offline-model"


@pytest.mark.parametrize(
    "config",
    [
        {"model": "m", "credential_source": "stored", "api_key": "must-not-be-in-json"},
        {"model": "https://example.test", "credential_source": "other"},
        {
            "model": "m",
            "credential_source": "environment",
            "base_url": "http://127.0.0.1",
        },
    ],
)
def test_unknown_config_fields_and_sources_are_not_silently_ignored(config):
    with pytest.raises(ProviderConfigurationError):
        model_config("llm", config)


@pytest.mark.parametrize("kind", ["llm", "image", "video", "embedding"])
async def test_selected_model_and_key_are_used_in_actual_http_payload(
    master, monkeypatch, kind
):
    import httpx

    from app.clients import provider_factory as clients

    fake = AsyncMock()
    fake.__aenter__.return_value = fake
    body = (
        {"choices": [{"message": {"content": "OK"}}], "usage": {}}
        if kind == "llm"
        else {"output": {"embeddings": [{"embedding": [0.01] * 1024}]}}
    )
    fake.post.return_value = httpx.Response(
        200 if kind in ["llm", "embedding"] else 500, json=body
    )
    monkeypatch.setattr(clients.httpx, "AsyncClient", lambda **kwargs: fake)
    monkeypatch.setattr(settings, "ALLOW_MOCK_ASSETS", False)
    provider = row(master, kind="llm" if kind == "embedding" else kind)
    if kind == "embedding":
        provider.config["embedding_model"] = "offline-embedding-model"
    async with provider_scope("tenant-a", database([provider])):
        if kind == "llm":
            await ProviderFactory.get_llm_client().chat_completion(
                [{"role": "user", "content": "test"}], model="hard-coded-node-model"
            )
        elif kind == "embedding":
            await ProviderFactory.get_llm_client().get_embedding("test")
        else:
            with pytest.raises(clients.ProviderCallError):
                if kind == "image":
                    await ProviderFactory.get_image_client().generate_images("test")
                else:
                    await ProviderFactory.get_video_client().generate_video("test")
    assert (
        fake.post.call_args.kwargs["headers"]["Authorization"]
        == "Bearer offline-test-secret"
    )
    assert fake.post.call_args.kwargs["json"]["model"] == (
        "offline-embedding-model" if kind == "embedding" else "offline-model"
    )


async def test_snapshot_rejects_unexpected_cross_tenant_record(master):
    with pytest.raises(ProviderConfigurationError):
        async with provider_scope(
            "tenant-a", database([row(master, "tenant-b", "provider-b")])
        ):
            pytest.fail("Unexpected cross-tenant record was accepted")
