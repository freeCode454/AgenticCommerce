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
from app.models import ComplianceReport, Copy, Sku, Task, Tenant, User
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


@pytest.mark.parametrize("valid", [True, False])
async def test_generated_copy_persists_validated_fields_with_tenant(context, monkeypatch, valid):
    import json
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from sqlalchemy import select

    from app.agent.nodes import creative_planner
    from app.core.generation import GenerationOutputError

    draft = {
        "title": "Ceramic Mug for Daily Use",
        "bullets": [f"Verified ceramic mug detail {i}" for i in range(1, 6)],
        "description": "A ceramic mug described using the supplied product facts.",
        "keywords": ["ceramic mug", "drinkware", "mug", "ceramic cup", "everyday cup"],
    }
    llm, recorder = AsyncMock(), AsyncMock()
    llm.chat_completion.return_value = {"content": json.dumps(draft) if valid else "INVALID COPY", "is_mock": 0}

    @asynccontextmanager
    async def node_session():
        yield context["session"]

    monkeypatch.setattr(creative_planner, "AsyncSessionLocal", node_session)
    monkeypatch.setattr(creative_planner.ProviderFactory, "get_llm_client", lambda *args: llm)
    monkeypatch.setattr(creative_planner, "record_node_execution", recorder)
    state = {"tenant_id": context["tenant_a"], "task_id": context["task"], "sku_id": context["sku_a"],
             "sku_data": {"name": "Ceramic Mug", "category": "home", "specs": {"material": "ceramic"}}}
    if valid:
        await creative_planner.creative_planner_node(state)
    else:
        with pytest.raises(GenerationOutputError):
            await creative_planner.creative_planner_node(state)
    rows = (await context["session"].execute(select(Copy).where(
        Copy.tenant_id == context["tenant_a"], Copy.task_id == context["task"], Copy.is_deleted == 0,
    ))).scalars().all()
    assert len(rows) == (1 if valid else 0)
    if valid:
        copy = rows[0]
        assert copy.sku_id == context["sku_a"]
        assert {key: getattr(copy, key) for key in draft} == draft
        detail = await context["client"].get("/api/v1/tasks/" + context["task"])
        assert detail.json()["data"]["copy"] == draft
    assert recorder.call_args.kwargs["status"] == ("success" if valid else "failed")


async def test_completed_task_without_review_cannot_export(context):
    response = await context["client"].post("/api/v1/packages/export",json={"task_id":context["task"]})
    assert response.status_code == 409


async def test_unimplemented_listing_is_not_written_and_legacy_record_is_local(context):
    from app.models.listing import Listing

    client, session = context["client"], context["session"]
    response = await client.post("/api/v1/listings", json={
        "sku_id": context["sku_a"], "platform": "amazon", "listing_data": {},
    })
    assert response.status_code == 501
    assert (await client.get("/api/v1/listings")).json()["data"]["total"] == 0

    session.add(Listing(
        tenant_id=context["tenant_a"], sku_id=context["sku_b"], platform="amazon",
        status="published", listing_data={"external_product_id": "EXT_legacy", "title": "Old listing"},
    ))
    await session.flush()
    [record] = (await client.get("/api/v1/listings")).json()["data"]["items"]
    assert record["status"] == "local_record"
    assert record["sku_name"] == record["sku_code"] == ""
    assert record["listing_data"] == {"title": "Old listing"}


@pytest.mark.parametrize("config", [{"platform": "shopify"}, {"language": "zh"}, {"media_type": "image"}])
async def test_task_rejects_unsupported_generation_config(context, config):
    response = await context["client"].post("/api/v1/tasks", json={"sku_id": context["sku_a"], "config": config})
    assert response.status_code == 422


async def test_zip_requires_current_review_and_archived_round(context, monkeypatch):
    from io import BytesIO
    import json
    from zipfile import ZipFile

    from app.api.v1 import assets as asset_api, packages
    from app.models.asset import Asset

    client, session = context["client"], context["session"]
    task_id, tenant_id = context["task"], context["tenant_a"]
    task = await session.get(Task, task_id)
    task.execution_id = uuid.uuid4().hex
    task.retry_count = 1
    common = {"tenant_id": tenant_id, "sku_id": context["sku_a"], "task_id": task_id,
              "execution_id": task.execution_id}
    copy = Copy(**common, title="Approved copy")
    review = ComplianceReport(**common, score=98, passed=1, status="passed")
    assets = [
        Asset(**common, type=kind, sub_type=subtype, generation_round=1, status="completed",
              url="https://expired.example.test/file")
        for kind, subtype in packages.DELIVERY_MEDIA
    ]
    previous = Asset(
        **common, type="image", sub_type="main", generation_round=0, status="completed",
        url="https://expired.example.test/old",
    )
    session.add_all([copy, review, previous, *assets])
    await session.flush()

    url = f"/api/v1/packages/{task_id}/download"
    manifest = (await client.post("/api/v1/packages/export", json={"task_id": task_id})).json()["data"]
    assert manifest["download_archive_url"] is None
    assert "正在归档" in manifest["download_block_reason"]
    assert (await client.get(url)).status_code == 409

    stored = {}
    for asset in assets:
        asset.archive_key = asset.id
        stored[asset.id] = f"fixture-{asset.sub_type}".encode()
        asset.archive_size = len(stored[asset.id])
        asset.archive_content_type = "image/png" if asset.type == "image" else "video/mp4"
    await session.flush()

    def read_object(key, size):
        assert len(stored[key]) == size
        yield stored[key]

    monkeypatch.setattr(packages, "iter_object", read_object)
    monkeypatch.setattr(asset_api, "iter_object", read_object)
    manifest = (await client.post("/api/v1/packages/export", json={"task_id": task_id})).json()["data"]
    assert manifest["download_archive_url"] == url
    assert len(manifest["media_assets"]) == 4
    response = await client.get(url)
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as bundle:
        assert set(bundle.namelist()) == {
            "copy.json", "review.json", "image/main.png", "image/detail.png", "image/scene.png",
            "video/product_showcase.mp4",
        }
        assert json.loads(bundle.read("copy.json"))["title"] == "Approved copy"
        assert bundle.read("image/main.png") == b"fixture-main"
        assert json.loads(bundle.read("review.json"))["passed"] == 1

    media_url = manifest["media_assets"][0]["url"]
    assert (await client.get(media_url)).status_code == 200
    assert (await client.get(media_url, headers={"Authorization": ""})).status_code == 401
    assets[0].tenant_id = context["tenant_b"]
    await session.flush()
    assert (await client.get(f"/api/v1/assets/{assets[0].id}/file")).status_code == 404
    assets[0].tenant_id = tenant_id
    await session.flush()

    previous.is_deleted = 1
    for asset in assets:
        asset.generation_round = None
    await session.flush()
    assert (await client.get(url)).status_code == 409
    for asset in assets:
        asset.generation_round = 1
    await session.flush()

    response = await client.put(f"/api/v1/copies/{copy.id}", json={"title": "Pending new review"})
    assert response.status_code == 200
    assert (await client.get(url)).status_code == 409


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


@pytest_asyncio.fixture
async def provider_context(context, monkeypatch):
    from app.core.provider_keys import encrypt_api_key, new_encryption_key
    from app.models.provider import Provider
    key = new_encryption_key()
    monkeypatch.setattr(settings, "PROVIDER_ENCRYPTION_KEY", key)
    rows=[]
    for tenant,secret,default in [(context["tenant_a"],"offline-tenant-a-key",1),(context["tenant_a"],"offline-standby-key",0),(context["tenant_b"],"offline-tenant-b-key",1)]:
        ident=uuid.uuid4().hex
        rows.append(Provider(id=ident,tenant_id=tenant,type="llm",name="Offline provider",api_key_enc=encrypt_api_key(secret,tenant,ident,key),config={"model":"offline-"+secret,"credential_source":"stored","embedding_model":"offline-embedding"},is_default=default))
    context["session"].add_all(rows)
    await context["session"].flush()
    return {**context,"default":rows[0],"standby":rows[1],"other":rows[2],"master":key}


async def test_provider_key_write_is_encrypted_and_api_never_returns_secrets(provider_context):
    from app.core.provider_keys import decrypt_api_key
    ctx=provider_context
    secret="offline-new-sensitive-api-key"
    result=await ctx["client"].put('/api/v1/providers/'+ctx["default"].id,json={"api_key":secret})
    assert result.status_code==200
    await ctx["session"].refresh(ctx["default"])
    ciphertext=ctx["default"].api_key_enc
    assert secret not in ciphertext
    assert decrypt_api_key(ciphertext,ctx["tenant_a"],ctx["default"].id,ctx["master"])==secret
    listing=await ctx["client"].get('/api/v1/providers')
    assert listing.status_code==200 and secret not in listing.text and ciphertext not in listing.text
    items=listing.json()["data"]["items"]
    assert len(items)==2
    assert all(item["key_status"]=="encrypted" for item in items)


async def test_default_switch_does_not_modify_other_tenant_and_clear_never_falls_back(provider_context, monkeypatch):
    from app.clients.provider_factory import ProviderFactory
    from app.services.provider_runtime import provider_scope
    ctx=provider_context
    response=await ctx["client"].put('/api/v1/providers/'+ctx["standby"].id,json={"is_default":1})
    assert response.status_code==200
    for name in ['default','standby','other']:await ctx["session"].refresh(ctx[name])
    assert (ctx['default'].is_default,ctx['standby'].is_default,ctx['other'].is_default)==(0,1,1)
    async with provider_scope(ctx['tenant_a'],ctx['session']):
        assert ProviderFactory.get_llm_client().api_key=='offline-standby-key'
    response=await ctx['client'].put('/api/v1/providers/'+ctx['standby'].id,json={'api_key':''})
    assert response.status_code==200
    monkeypatch.setattr(settings,'DASHSCOPE_API_KEY','offline-server-key')
    async with provider_scope(ctx['tenant_a'],ctx['session']):
        assert ProviderFactory.get_llm_client().api_key==''
    assert (await ctx['client'].post('/api/v1/providers/'+ctx['standby'].id+'/test')).status_code==503


@pytest.mark.parametrize('operation',['put','post'])
async def test_provider_write_and_test_reject_other_tenant(provider_context,operation):
    ctx=provider_context
    path='/api/v1/providers/'+ctx['other'].id+('/test' if operation=='post' else '')
    result=await getattr(ctx['client'],operation)(path,**({'json':{'api_key':'offline-stolen'}} if operation=='put' else {}))
    assert result.status_code==404


@pytest.mark.parametrize('operation',['put','post'])
async def test_operator_cannot_edit_or_test_provider(provider_context,operation):
    ctx=provider_context
    token=create_access_token({'user_id':ctx['operator'],'tenant_id':ctx['tenant_a']})
    path='/api/v1/providers/'+ctx['default'].id+('/test' if operation=='post' else '')
    result=await getattr(ctx['client'],operation)(path,headers={'Authorization':'Bearer '+token},**({'json':{'api_key':'offline-key'}} if operation=='put' else {}))
    assert result.status_code==403


async def test_provider_test_uses_selected_standby_not_default(provider_context,monkeypatch):
    from app.clients.provider_factory import QwenLLMClient
    ctx=provider_context
    observed=[]
    async def fake(self,*args,**kwargs):
        observed.append((self.api_key,self.model))
        return {'content':'OK','is_mock':0,'model':self.model,'elapsed_ms':7}
    monkeypatch.setattr(QwenLLMClient,'chat_completion',fake)
    result=await ctx['client'].post('/api/v1/providers/'+ctx['standby'].id+'/test')
    assert result.status_code==200
    assert observed==[('offline-standby-key',ctx['standby'].config['model'])]
    assert result.json()['data']['provider_id']==ctx['standby'].id


async def test_legacy_secret_is_masked_then_encrypted_on_save(provider_context):
    from app.models.provider import Provider
    ctx=provider_context
    secret='offline-legacy-plaintext-key'
    legacy=Provider(id=uuid.uuid4().hex,tenant_id=ctx['tenant_a'],type='image',name='Legacy image',api_key_enc=secret,config={'model':'old-image-model','api_key':'offline-json-secret'},is_default=1)
    ctx['session'].add(legacy);await ctx['session'].flush()
    listed=await ctx['client'].get('/api/v1/providers')
    assert secret not in listed.text and 'offline-json-secret' not in listed.text
    entry=next(item for item in listed.json()['data']['items'] if item['id']==legacy.id)
    assert entry['configuration_status']=='pending' and entry['key_status']=='legacy'
    assert (await ctx['client'].post('/api/v1/providers/'+legacy.id+'/test')).status_code==503
    saved=await ctx['client'].put('/api/v1/providers/'+legacy.id,json={'config':{'model':'qwen-image-3.0-pro','credential_source':'stored'}})
    assert saved.status_code==200
    await ctx['session'].refresh(legacy)
    assert legacy.api_key_enc.startswith('enc:v1:') and secret not in legacy.api_key_enc


async def test_invalid_requests_do_not_echo_credentials(provider_context):
    ctx=provider_context
    secret='offline-sensitive-'*20
    for payload in [{'api_key':secret},{'api_key':{'private_value':secret}},{'api_key':'short-key','is_default':True}]:
        result=await ctx['client'].put('/api/v1/providers/'+ctx['default'].id,json=payload)
        assert result.status_code in [422,503]
        assert secret not in result.text
    rejected=await ctx['client'].put('/api/v1/providers/'+ctx['default'].id,json={'config':{'model':'m','credential_source':'stored','api_key':secret}})
    assert rejected.status_code==503 and secret not in rejected.text


@pytest.mark.parametrize('path,payload',[
    ('/api/v1/skus/extract-specs',{'description':'A ceramic mug'}),
    ('/api/v1/compliance/check',{'title':'Ceramic Mug','content':'A mug with known facts'}),
    ('/api/v1/skus',{'code':'OFFLINE-AUTO','name':'Ceramic Mug','category':'home','description':'A ceramic mug','specs':{}}),
])
async def test_authenticated_model_operations_bind_tenant_provider(provider_context,monkeypatch,path,payload):
    import json

    from app.clients.provider_factory import QwenLLMClient
    ctx=provider_context
    observed=[]
    async def fake(self,*args,**kwargs):
        observed.append((self.api_key,self.model))
        result={'score':95,'passed':1,'violations':[],'suggestions':[]} if 'compliance' in path else {'material':'ceramic'}
        return {'content':json.dumps(result),'is_mock':0,'model':self.model}
    monkeypatch.setattr(QwenLLMClient,'chat_completion',fake)
    result=await ctx['client'].post(path,json=payload)
    assert result.status_code==200
    assert observed==[('offline-tenant-a-key',ctx['default'].config['model'])]


async def test_knowledge_index_and_query_use_tenant_embedding_configuration(provider_context,monkeypatch):
    from app.clients.provider_factory import QwenLLMClient
    ctx=provider_context
    observed=[]
    async def fake(self,*args,**kwargs):
        observed.append((self.api_key,self.embedding_model))
        return [0.01]*1024
    monkeypatch.setattr(QwenLLMClient,'get_embedding',fake)
    created=await ctx['client'].post('/api/v1/knowledge/docs',json={'name':'Offline doc','category':'brand','doc_type':'brand','content':'Verified brand facts'})
    queried=await ctx['client'].post('/api/v1/knowledge/query',json={'query_text':'brand facts','top_k':1})
    assert created.status_code==queried.status_code==200
    assert observed==[('offline-tenant-a-key','offline-embedding')]*2


async def test_background_workflow_has_independent_tenant_snapshot(provider_context,monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agent import graph
    from app.clients.provider_factory import ProviderFactory
    from app.services import provider_runtime, task_worker
    from app.services.task_worker import execute_workflow
    ctx=provider_context
    observed=[]
    @asynccontextmanager
    async def session():yield ctx['session']
    async def execute(state):
        observed.append((ProviderFactory.get_llm_client().api_key,state['tenant_id']))
        return {}
    monkeypatch.setattr(task_worker,'AsyncSessionLocal',session)
    monkeypatch.setattr(provider_runtime,'AsyncSessionLocal',session)
    monkeypatch.setattr(graph,'app_workflow',SimpleNamespace(ainvoke=AsyncMock(side_effect=execute)))
    await execute_workflow(ctx['task'],ctx['tenant_a'],ctx['sku_a'],{'media_type':'both'})
    assert observed==[('offline-tenant-a-key',ctx['tenant_a'])]


async def test_bad_image_key_does_not_block_llm_only_operation(provider_context,monkeypatch):
    from app.clients.provider_factory import QwenLLMClient
    from app.models.provider import Provider
    ctx=provider_context
    ctx['session'].add(Provider(id=uuid.uuid4().hex,tenant_id=ctx['tenant_a'],type='image',name='Invalid image config',api_key_enc='enc:v1:unreadable',config={'model':'image-model','credential_source':'stored'},is_default=1))
    await ctx['session'].flush()
    async def fake(self,*args,**kwargs):return {'content':'{"material":"ceramic"}','is_mock':0}
    monkeypatch.setattr(QwenLLMClient,'chat_completion',fake)
    result=await ctx['client'].post('/api/v1/skus/extract-specs',json={'description':'A ceramic mug'})
    assert result.status_code==200


async def test_legacy_key_migration_is_scoped_idempotent_and_does_not_activate(provider_context,monkeypatch):
    from contextlib import asynccontextmanager

    from app.models.provider import Provider
    from app.scripts import encrypt_provider_keys
    ctx=provider_context
    rows=[Provider(id=uuid.uuid4().hex,tenant_id=tenant,type='video',name='Old config',api_key_enc='offline-legacy-key',config={'model':'old-model'},is_default=1) for tenant in [ctx['tenant_a'],ctx['tenant_b']]]
    ctx['session'].add_all(rows);await ctx['session'].flush()
    @asynccontextmanager
    async def session():yield ctx['session']
    monkeypatch.setattr(encrypt_provider_keys,'AsyncSessionLocal',session)
    assert await encrypt_provider_keys.migrate_keys(ctx['tenant_a'])==1
    assert rows[0].api_key_enc=='offline-legacy-key'
    assert await encrypt_provider_keys.migrate_keys(ctx['tenant_a'],apply=True)==1
    assert await encrypt_provider_keys.migrate_keys(ctx['tenant_a'],apply=True)==0
    assert rows[0].api_key_enc.startswith('enc:v1:')
    assert rows[1].api_key_enc=='offline-legacy-key'
    assert rows[0].config=={'model':'old-model'}


async def test_saving_model_without_replacing_key_preserves_ciphertext(provider_context):
    from app.clients.provider_factory import ProviderFactory
    from app.services.provider_runtime import provider_scope
    ctx=provider_context
    ciphertext=ctx['default'].api_key_enc
    result=await ctx['client'].put('/api/v1/providers/'+ctx['default'].id,json={'config':{'model':'updated-model','credential_source':'stored','embedding_model':'updated-embedding'}})
    assert result.status_code==200
    await ctx['session'].refresh(ctx['default'])
    assert ctx['default'].api_key_enc==ciphertext
    async with provider_scope(ctx['tenant_a'],ctx['session']):
        client=ProviderFactory.get_llm_client()
        assert (client.model,client.embedding_model,client.api_key)==('updated-model','updated-embedding','offline-tenant-a-key')


async def test_embedding_model_change_does_not_mix_old_and_new_vectors(provider_context,monkeypatch):
    from app.clients.provider_factory import QwenLLMClient
    from app.models.knowledge import KnowledgeBaseDoc, KnowledgeChunk
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.services.knowledge_service import KnowledgeService
    ctx=provider_context
    doc=KnowledgeBaseDoc(id=uuid.uuid4().hex,tenant_id=ctx['tenant_a'],category='brand',doc_type='brand',name='Offline vectors',vector_status='indexed')
    ctx['session'].add(doc);await ctx['session'].flush()
    for model in [None,'text-embedding-v4','offline-embedding']:
        ctx['session'].add(KnowledgeChunk(id=uuid.uuid4().hex,tenant_id=ctx['tenant_a'],doc_id=doc.id,doc_type='brand',chunk_index=1,content=model or 'legacy-v4',embedding=[0.01]*1024,metadata_json={} if model is None else {'embedding_model':model}))
    await ctx['session'].flush()
    async def fake(self,*args,**kwargs):return [0.01]*1024
    monkeypatch.setattr(QwenLLMClient,'get_embedding',fake)
    matches=await KnowledgeService(ctx['session']).vector_search(ctx['tenant_a'],'facts',10)
    assert [item['content'] for item in matches]==['offline-embedding']
    repo=KnowledgeRepository(ctx['session'])
    matches=await repo.search_vectors(ctx['tenant_a'],[0.01]*1024,limit=10,embedding_model='text-embedding-v4')
    assert {item.content for item in matches}=={'legacy-v4','text-embedding-v4'}
