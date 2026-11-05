"""Run only against a migrated, disposable *_test database with RUN_DB_TESTS=1."""
import os
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.conf.config import settings
from app.core.deps import get_db
from app.core.security import create_access_token, get_password_hash
from app.models import Tenant, User, Sku, Task, Copy, ComplianceReport
from main import app


@pytest_asyncio.fixture
async def context():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 and POSTGRES_DB to a migrated *_test database")
    assert settings.APP_ENV in {"dev", "test"} and settings.POSTGRES_DB.endswith("_test")
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
            tenant_a, tenant_b, admin_id, operator_id, sku_a, sku_b, task_a = [uuid.uuid4().hex for _ in range(7)]
            session.add_all([
                Tenant(id=tenant_a,name="Test A"), Tenant(id=tenant_b,name="Test B"),
                User(id=admin_id,tenant_id=tenant_a,email=admin_id+"@example.test",name="Admin",role="admin",password=get_password_hash("offline-test-password")),
                User(id=operator_id,tenant_id=tenant_a,email=operator_id+"@example.test",name="Operator",role="operator",password="unused"),
                Sku(id=sku_a,tenant_id=tenant_a,code="TEST-A",name="A",category="test",specs={}),
                Sku(id=sku_b,tenant_id=tenant_b,code="TEST-B",name="B",category="test",specs={}),
                Task(id=task_a,tenant_id=tenant_a,sku_id=sku_a,status="completed",config={}),
            ])
            await session.flush()

            async def override_db():
                yield session

            app.dependency_overrides[get_db] = override_db
            token = create_access_token({"user_id":admin_id,"tenant_id":tenant_a})
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://localhost",headers={"Authorization":"Bearer "+token}) as client:
                try:
                    yield {"client":client,"session":session,"tenant_a":tenant_a,"tenant_b":tenant_b,"admin":admin_id,"operator":operator_id,"sku_a":sku_a,"sku_b":sku_b,"task":task_a}
                finally:
                    app.dependency_overrides.clear()
        await transaction.rollback()
    await engine.dispose()


async def test_batch_cannot_reference_another_tenants_sku(context):
    response = await context["client"].post("/api/v1/batches",json={"name":"cross tenant","sku_ids":[context["sku_b"]],"config":{}})
    assert response.status_code in {400,404}
    own = await context["client"].get("/api/v1/skus/"+context["sku_a"])
    assert own.status_code == 200
    assert (await context["client"].get("/api/v1/skus/"+context["sku_b"])).status_code == 404


async def test_asset_cannot_reference_another_tenants_sku(context):
    response = await context["client"].post("/api/v1/assets",json={"sku_id":context["sku_b"],"type":"image","url":"https://assets.example.test/item.png"})
    assert response.status_code == 404


async def test_token_cannot_substitute_tenant(context):
    forged_context = create_access_token({"user_id":context["admin"],"tenant_id":context["tenant_b"]})
    response = await context["client"].get("/api/v1/auth/me",headers={"Authorization":"Bearer "+forged_context})
    assert response.status_code == 401


async def test_current_database_role_controls_provider_access(context):
    token = create_access_token({"user_id":context["operator"],"tenant_id":context["tenant_a"],"role":"admin"})
    response = await context["client"].get("/api/v1/providers",headers={"Authorization":"Bearer "+token})
    assert response.status_code == 403


async def test_disabled_user_cannot_reuse_issued_token(context):
    user = await context["session"].get(User, context["admin"])
    user.status = "disabled"
    await context["session"].flush()
    assert (await context["client"].get("/api/v1/auth/me")).status_code == 401


async def test_disabled_tenant_cannot_reuse_issued_token(context):
    tenant = await context["session"].get(Tenant, context["tenant_a"])
    tenant.status = "disabled"
    await context["session"].flush()
    assert (await context["client"].get("/api/v1/auth/me")).status_code == 401


async def test_completed_task_without_review_cannot_export(context):
    response = await context["client"].post("/api/v1/packages/export",json={"task_id":context["task"]})
    assert response.status_code == 409


async def test_editing_copy_invalidates_previous_approval(context):
    copy = Copy(tenant_id=context["tenant_a"],task_id=context["task"],sku_id=context["sku_a"],title="Old")
    report = ComplianceReport(tenant_id=context["tenant_a"],task_id=context["task"],sku_id=context["sku_a"],score=99,passed=1,status="passed")
    context["session"].add_all([copy,report])
    await context["session"].flush()
    response = await context["client"].put("/api/v1/copies/"+copy.id,json={"title":"Edited"})
    assert response.status_code == 200
    await context["session"].refresh(report)
    assert report.passed == 0 and report.status == "outdated"
    assert (await context["client"].post("/api/v1/packages/export",json={"task_id":context["task"]})).status_code == 409
