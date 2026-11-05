import json
import time
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.conf.config import Settings, settings
from app.core.security import create_access_token, decode_token
from app.clients import provider_factory as providers
from app.agent.nodes import quality_reviewer as reviewer
from app.api.v1.ws import ConnectionManager
from app.api.task_config import TaskConfig
from app.api.v1.batches import BatchCreateRequest
from main import app


@pytest.fixture(autouse=True)
def safe_settings(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "offline-test-key-" * 4)


@pytest.mark.parametrize("path,method", [("/api/v1/auth/me", "get"), ("/api/v1/auth/refresh", "post"), ("/api/v1/tasks", "get")])
def test_anonymous_requests_are_rejected(path, method):
    with TestClient(app, base_url="http://localhost") as client:
        response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("payload", [
    {"user_id": "u"}, {"user_id": "", "tenant_id": "t"},
    {"user_id": "u", "tenant_id": "t", "type": "refresh"},
])
def test_invalid_identity_claims_are_rejected(payload):
    claims = {"exp": time.time() + 60, "type": "access", **payload}
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)


def test_expired_access_token_is_rejected():
    token = create_access_token({"user_id": "u", "tenant_id": "t"}, timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


@pytest.mark.parametrize("overrides", [
    {"DEBUG": True}, {"ALLOW_MOCK_ASSETS": True}, {"AUTH_ENABLED": False},
    {"SECRET_KEY": "short"}, {"SECRET_KEY": Settings.model_fields["SECRET_KEY"].default},
    {"CORS_ORIGINS": ["*"]}, {"POSTGRES_PASSWORD": "postgres"},
])
def test_production_rejects_unsafe_configuration(overrides):
    config = dict(APP_ENV="prod", DEBUG=False, ALLOW_MOCK_ASSETS=False,
                  AUTH_ENABLED=True, SECRET_KEY="production-test-key-" * 4,
                  POSTGRES_PASSWORD="synthetic-db-password", MINIO_SECRET_KEY="synthetic-storage-secret")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**config, **overrides})


def test_configuration_errors_do_not_print_secrets():
    secret = "never-log-this-synthetic-credential"
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, APP_ENV="prod", DEBUG=True, DASHSCOPE_API_KEY=secret)
    assert secret not in str(exc.value)
    assert secret not in repr(Settings(_env_file=None, APP_ENV="test", DASHSCOPE_API_KEY=secret))


@pytest.mark.parametrize("config", [{"max_retries":-1},{"max_retries":100},{"max_retries":True},{"media_type":"anything"}])
def test_generation_parameters_are_bounded(config):
    with pytest.raises(ValidationError):
        TaskConfig(**config)


def test_batch_size_is_bounded():
    with pytest.raises(ValidationError):
        BatchCreateRequest(name="oversized", sku_ids=["id"] * 101)


async def test_production_cannot_mock_even_if_flag_is_mutated(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "ALLOW_MOCK_ASSETS", True)
    client = providers.QwenLLMClient()
    client.api_key = ""
    with pytest.raises(providers.ProviderCallError):
        await client.chat_completion([{"role":"user","content":"offline"}])


@pytest.mark.parametrize("kind", ["llm", "embedding", "image", "video"])
async def test_no_key_cannot_mock_when_disabled(monkeypatch, kind):
    monkeypatch.setattr(settings, "ALLOW_MOCK_ASSETS", False)
    client = {"llm": providers.QwenLLMClient, "embedding": providers.QwenLLMClient,
              "image": providers.WanxImageClient, "video": providers.KlingVideoClient}[kind]()
    client.api_key = ""
    with pytest.raises(providers.ProviderCallError):
        if kind == "llm":
            await client.chat_completion([{"role": "user", "content": "offline"}])
        elif kind == "embedding":
            await client.get_embedding("offline")
        elif kind == "image":
            await client.generate_images("offline")
        else:
            await client.generate_video("offline")


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_provider_error_cannot_turn_into_mock_success(monkeypatch, status):
    monkeypatch.setattr(settings, "ALLOW_MOCK_ASSETS", False)
    fake = AsyncMock()
    fake.__aenter__.return_value = fake
    fake.post.return_value = httpx.Response(status, json={"error": "offline"})
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: fake)
    with pytest.raises(providers.ProviderCallError):
        await providers.QwenLLMClient(api_key="synthetic-test-key").chat_completion([{"role": "user", "content": "offline"}])


@pytest.mark.parametrize("content,is_mock,expected", [
    ("invalid JSON", False, False),
    ('{"score":99,"passed":0,"violations":[],"suggestions":[]}', False, False),
    ('{"score":99,"passed":1,"violations":[],"suggestions":[]}', True, False),
    ('{"score":99,"passed":1,"violations":[],"suggestions":[]}', False, True),
    ('{"score":99,"violations":[],"suggestions":[]}', False, False),
    ('{"score":999,"passed":1,"violations":[],"suggestions":[]}', False, False),
])
async def test_review_is_fail_closed(monkeypatch, content, is_mock, expected):
    llm = AsyncMock()
    llm.chat_completion.return_value = {"content": content, "is_mock": is_mock}
    monkeypatch.setattr(reviewer.ProviderFactory, "get_llm_client", lambda *args: llm)
    monkeypatch.setattr(reviewer, "record_node_execution", AsyncMock())
    result = await reviewer.quality_reviewer_node({
        "creative_plan": {"title": "Ceramic mug"}, "config": {"media_type": "image"},
        "generated_images": [{"url": "https://assets.example.test/image.png", "is_mock": 0}],
    })
    assert result["is_passed"] is expected


async def test_rule_scan_cannot_be_overridden_by_high_model_score(monkeypatch):
    llm = AsyncMock()
    llm.chat_completion.return_value = {"content": json.dumps({"score":99,"passed":1,"violations":[],"suggestions":[]})}
    monkeypatch.setattr(reviewer.ProviderFactory, "get_llm_client", lambda *args: llm)
    monkeypatch.setattr(reviewer, "record_node_execution", AsyncMock())
    result = await reviewer.quality_reviewer_node({"creative_plan":{"title":"100% cure"}})
    assert result["is_passed"] is False


async def test_broadcast_is_isolated_by_tenant_and_task():
    manager = ConnectionManager()
    owned, other_tenant, other_task = AsyncMock(), AsyncMock(), AsyncMock()
    for connection, tenant, task in [(owned,"a","one"),(other_tenant,"b","one"),(other_task,"a","two")]:
        manager.connect(connection, tenant, task, time.time()+60)
    event = {"type":"node_update","task_id":"one","payload":{"status":"success"}}
    await manager.broadcast(event, tenant_id="a")
    owned.send_json.assert_awaited_once_with(event)
    other_tenant.send_json.assert_not_awaited()
    other_task.send_json.assert_not_awaited()


def test_websocket_requires_authentication():
    with TestClient(app, base_url="http://localhost") as client:
        with client.websocket_connect("ws://localhost/api/v1/ws/tasks/offline") as ws:
            ws.send_json({"type":"ping"})
            assert ws.receive()["code"] == 4401


def test_readiness_reports_failed_dependencies(monkeypatch):
    from app.services import health_service
    monkeypatch.setattr(health_service, "dependency_status", AsyncMock(return_value={"postgres":"unavailable","redis":"ready","storage":"ready"}))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"
