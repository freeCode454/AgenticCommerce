"""Fault/concurrency tests against an explicitly isolated, migrated *_test DB.

All runners are local stubs. No provider is contacted, including crash tests.
"""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.conf.config import settings
from app.core.task_execution import (
    ExecutionContext,
    ExecutionSupersededError,
    active_execution,
    fence_execution,
)
from app.models import (
    Asset,
    Batch,
    ComplianceReport,
    Copy,
    ProviderJob,
    Sku,
    Task,
    TaskExecution,
    TaskNodeRun,
    Tenant,
)
from app.services.batch_service import BatchService
from app.services.task_queue import TaskConflictError
from app.services.task_service import TaskService
from app.services.task_worker import INTERRUPTED, TaskWorker


@pytest_asyncio.fixture
async def queue_db(monkeypatch):
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Requires RUN_DB_TESTS=1 and a disposable *_test database")
    assert settings.APP_ENV in {"dev", "test"} and settings.POSTGRES_DB.endswith(
        "_test"
    )
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    from app.core.provider_keys import new_encryption_key
    from app.services import remote_video, workflow_checkpoint

    monkeypatch.setattr(settings, "PROVIDER_ENCRYPTION_KEY", new_encryption_key())
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "offline-queue-key")
    monkeypatch.setattr(settings, "WANX_API_KEY", "offline-queue-image-key")
    monkeypatch.setattr(remote_video, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(workflow_checkpoint, "AsyncSessionLocal", sessions)
    a, b, sku_a, sku_b = (uuid4().hex for _ in range(4))
    async with sessions() as session:
        session.add_all(
            [
                Tenant(id=a, name="Queue test A"),
                Tenant(id=b, name="Queue test B"),
                Sku(
                    id=sku_a,
                    tenant_id=a,
                    code="QUEUE-A",
                    name="Ceramic mug",
                    category="home",
                    specs={},
                ),
                Sku(
                    id=sku_b,
                    tenant_id=b,
                    code="QUEUE-B",
                    name="Other mug",
                    category="home",
                    specs={},
                ),
            ]
        )
        await session.commit()
    try:
        yield SimpleNamespace(
            engine=engine, sessions=sessions, a=a, b=b, sku_a=sku_a, sku_b=sku_b
        )
    finally:
        async with sessions() as session:
            for tenant_id in (a, b):
                for model in (
                    TaskNodeRun,
                    ProviderJob,
                    Copy,
                    Asset,
                    ComplianceReport,
                    TaskExecution,
                    Task,
                    Batch,
                    Sku,
                ):
                    await session.execute(
                        delete(model).where(model.tenant_id == tenant_id)
                    )
                await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await session.commit()
        await engine.dispose()


async def create(ctx, *, tenant=None, sku=None, key=None):
    async with ctx.sessions() as session:
        return await TaskService(session).create_task(
            tenant or ctx.a,
            None,
            sku or ctx.sku_a,
            config={"max_retries": 0},
            request_key=key,
        )


async def task_and_execution(ctx, task_id):
    async with ctx.sessions() as session:
        task = (
            await session.execute(
                select(Task).where(Task.id == task_id, Task.tenant_id == ctx.a)
            )
        ).scalar_one()
        execution = (
            await session.execute(
                select(TaskExecution).where(
                    TaskExecution.id == task.execution_id,
                    TaskExecution.tenant_id == ctx.a,
                )
            )
        ).scalar_one()
        return task, execution


def worker(ctx, runner=None, **kwargs):
    return TaskWorker(
        database_engine=ctx.engine,
        session_factory=ctx.sessions,
        runner=runner or AsyncMock(return_value={"is_passed": True}),
        **kwargs,
    )


async def test_canceled_queue_is_terminal_and_stale_cancel_cannot_stop_retry(queue_db):
    ctx = queue_db
    user_id = uuid4().hex
    async with ctx.sessions() as session:
        batch = await BatchService(session).create_batch(ctx.a, user_id, "Canceled batch", [ctx.sku_a])
        task_id = batch["tasks"][0]["task_id"]
    _, attempt = await task_and_execution(ctx, task_id)

    async with ctx.sessions() as session:
        with pytest.raises(LookupError):
            await TaskService(session).cancel_task(ctx.b, task_id, attempt.id, user_id)
    async with ctx.sessions() as session:
        svc = TaskService(session)
        canceled = await svc.cancel_task(ctx.a, task_id, attempt.id, user_id)
        assert canceled["status"] == "canceled"
        assert await svc.cancel_task(ctx.a, task_id, attempt.id, user_id) == canceled
        detail = await BatchService(session).get_batch_detail(ctx.a, batch["batch_id"])
        assert detail["batch"]["status"] == detail["tasks"][0]["status"] == "canceled"
        assert detail["batch"]["failed_count"] == 0

    task, saved = await task_and_execution(ctx, task_id)
    assert task.updated_by == saved.updated_by == user_id
    assert saved.status == "canceled" and saved.finished_at and saved.started_at is None
    runner = AsyncMock()
    assert not await worker(ctx, runner).run_one(ctx.a, task_id)
    runner.assert_not_awaited()

    async with ctx.sessions() as session:
        await TaskService(session).retrigger_task(ctx.a, task_id)
        with pytest.raises(TaskConflictError):
            await TaskService(session).cancel_task(ctx.a, task_id, attempt.id, user_id)
    task, replacement = await task_and_execution(ctx, task_id)
    assert task.status == replacement.status == "pending" and replacement.id != attempt.id


async def test_committed_queue_survives_worker_replacement(queue_db):
    ctx = queue_db
    created = await create(ctx)
    task, execution = await task_and_execution(ctx, created["task_id"])
    assert task.status == execution.status == "pending"
    assert len(task.id) == len(execution.id) == 32
    runner = AsyncMock(return_value={"is_passed": True})
    fresh_worker = worker(ctx, runner)
    assert await fresh_worker.run_one(ctx.a, task.id)
    task, execution = await task_and_execution(ctx, task.id)
    assert task.status == execution.status == "completed"
    assert execution.started_at and execution.finished_at
    runner.assert_awaited_once()


async def test_concurrent_create_replays_one_request_and_rejects_changed_payload(
    queue_db,
):
    ctx = queue_db
    first, second = await asyncio.gather(
        create(ctx, key="same-request"), create(ctx, key="same-request")
    )
    assert first["task_id"] == second["task_id"]
    async with ctx.sessions() as session:
        with pytest.raises(TaskConflictError):
            await TaskService(session).create_task(
                ctx.a,
                None,
                ctx.sku_a,
                config={"max_retries": 2},
                request_key="same-request",
            )
    async with ctx.sessions() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(TaskExecution)
            .where(TaskExecution.tenant_id == ctx.a)
        )
        assert count == 1


async def test_same_request_key_is_scoped_to_tenant(queue_db):
    ctx = queue_db
    first = await create(ctx, key="request")
    second = await create(ctx, tenant=ctx.b, sku=ctx.sku_b, key="request")
    assert first["task_id"] != second["task_id"]
    runner = AsyncMock(return_value={"is_passed": True})
    assert not await worker(ctx, runner).run_one(ctx.b, first["task_id"])
    runner.assert_not_awaited()


async def test_two_workers_cannot_execute_same_task_or_retrigger_while_running(
    queue_db,
):
    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def runner(**kwargs):
        calls.append(active_execution.get())
        entered.set()
        await release.wait()
        return {"is_passed": True}

    first = asyncio.create_task(worker(ctx, runner).run_one(ctx.a, task_id))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert not await worker(ctx, runner).run_one(ctx.a, task_id)
        async with ctx.sessions() as session:
            with pytest.raises(TaskConflictError):
                await TaskService(session).retrigger_task(ctx.a, task_id)
        assert len(calls) == 1 and calls[0].task_id == task_id
    finally:
        release.set()
        await first
    assert active_execution.get() is None


async def test_orphan_running_attempt_is_interrupted_without_replaying_model(queue_db):
    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    assert await worker(ctx).claim(
        ctx.a, task_id
    )  # Simulate process death after commit.
    runner = AsyncMock(return_value={"is_passed": True})
    assert not await worker(ctx, runner).run_one(ctx.a, task_id)
    task, execution = await task_and_execution(ctx, task_id)
    assert task.status == "failed" and execution.status == "interrupted"
    assert task.error_message == INTERRUPTED
    runner.assert_not_awaited()


async def test_lost_postgres_session_lock_cancels_execution_and_does_not_replay(
    queue_db, monkeypatch
):
    ctx = queue_db
    monkeypatch.setattr(settings, "TASK_WORKER_HEARTBEAT_SECONDS", 0.1)
    task_id = (await create(ctx))["task_id"]
    entered, cancelled, monitored = asyncio.Event(), asyncio.Event(), asyncio.Event()
    lock_pid = []

    async def runner(**kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    current = worker(ctx, runner)
    original = current.heartbeat

    async def heartbeat(connection):
        lock_pid.append(await connection.scalar(text("SELECT pg_backend_pid()")))
        await connection.commit()
        monitored.set()
        await original(connection)

    current.heartbeat = heartbeat
    job = asyncio.create_task(current.run_one(ctx.a, task_id))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.wait_for(monitored.wait(), 5)
        # Terminate only this test worker's database session, never the database/service.
        async with ctx.engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_terminate_backend(:pid)"), {"pid": lock_pid[0]}
            )
        await asyncio.wait_for(job, 8)
        assert cancelled.is_set()
        task, execution = await task_and_execution(ctx, task_id)
        assert task.status == "failed" and execution.status == "interrupted"
        again = AsyncMock()
        assert not await worker(ctx, again).run_one(ctx.a, task_id)
        again.assert_not_awaited()
    finally:
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)


async def test_shutdown_interrupts_running_job_but_keeps_queued_job(queue_db):
    ctx = queue_db
    ids = [(await create(ctx))["task_id"] for _ in range(2)]
    entered = asyncio.Event()

    async def runner(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    current = worker(ctx, runner, concurrency=1)
    await current.tick()
    await asyncio.wait_for(entered.wait(), 5)
    await current.stop()
    first, attempt = await task_and_execution(ctx, ids[0])
    second, queued = await task_and_execution(ctx, ids[1])
    assert first.status == "failed" and attempt.status == "interrupted"
    assert second.status == queued.status == "pending"
    assert await worker(ctx).run_one(ctx.a, second.id)


async def test_failed_runner_is_sanitized_and_is_not_automatically_retried(queue_db):
    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    runner = AsyncMock(side_effect=RuntimeError("sensitive-provider-response"))
    current = worker(ctx, runner)
    assert not await current.run_one(ctx.a, task_id)
    assert not await current.run_one(ctx.a, task_id)
    task, attempt = await task_and_execution(ctx, task_id)
    assert task.status == attempt.status == "failed"
    assert "sensitive-provider-response" not in task.error_message
    runner.assert_awaited_once()


async def test_retry_is_idempotent_and_hides_previous_attempt_outputs(queue_db):
    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    assert await worker(ctx).claim(ctx.a, task_id)
    _, old = await task_and_execution(ctx, task_id)
    async with ctx.sessions() as session:
        session.add_all(
            [
                Copy(
                    tenant_id=ctx.a,
                    task_id=task_id,
                    execution_id=old.id,
                    sku_id=ctx.sku_a,
                    title="Old result",
                    language="en",
                    bullets=[],
                    keywords=[],
                ),
                TaskNodeRun(
                    tenant_id=ctx.a,
                    task_id=task_id,
                    execution_id=old.id,
                    node_name="creative_planner",
                    status="success",
                    cost=0.01,
                ),
            ]
        )
        await session.commit()
    await worker(ctx).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        retried = await TaskService(session).retrigger_task(
            ctx.a, task_id, request_key="manual-retry"
        )
        detail = await TaskService(session).get_task_detail(ctx.a, task_id)
        assert detail["copy"] is None and detail["task"]["error_message"] is None
        assert await TaskService(session).get_node_runs(ctx.a, task_id) == []
    assert await worker(ctx).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        replayed = await TaskService(session).retrigger_task(
            ctx.a, task_id, request_key="manual-retry"
        )
        assert retried["task_id"] == replayed["task_id"]
        assert replayed["status"] == "completed"
        assert (
            await session.scalar(
                select(func.count())
                .select_from(TaskExecution)
                .where(TaskExecution.tenant_id == ctx.a)
            )
            == 2
        )
        assert (
            await session.scalar(
                select(func.sum(TaskNodeRun.cost)).where(TaskNodeRun.tenant_id == ctx.a)
            )
            == 0.01
        )


async def test_superseded_attempt_cannot_write_or_issue_new_model_request(
    queue_db, monkeypatch
):
    from app.clients import postgres
    from app.clients.provider_factory import QwenLLMClient

    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    await worker(ctx).claim(ctx.a, task_id)
    _, old = await task_and_execution(ctx, task_id)
    await worker(ctx).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        await TaskService(session).retrigger_task(ctx.a, task_id)
    monkeypatch.setattr(postgres, "AsyncSessionLocal", ctx.sessions)
    token = active_execution.set(ExecutionContext(ctx.a, task_id, old.id))
    try:
        async with ctx.sessions() as session:
            with pytest.raises(ExecutionSupersededError):
                await fence_execution(session)
        outbound = AsyncMock()
        monkeypatch.setattr(httpx.AsyncClient, "post", outbound)
        with pytest.raises(ExecutionSupersededError):
            await QwenLLMClient(api_key="offline-key").chat_completion([])
        outbound.assert_not_awaited()
    finally:
        active_execution.reset(token)


async def test_batch_reconciles_real_counts_and_retrigger_returns_to_pending(queue_db):
    ctx = queue_db
    async with ctx.sessions() as session:
        second = uuid4().hex
        session.add(
            Sku(
                id=second,
                tenant_id=ctx.a,
                code="QUEUE-A2",
                name="Second mug",
                category="home",
                specs={},
            )
        )
        await session.commit()
        created = await BatchService(session).create_batch(
            ctx.a, None, "Batch", [ctx.sku_a, second], request_key="batch-request"
        )
    async with ctx.sessions() as session:
        replay = await BatchService(session).create_batch(
            ctx.a, None, "Batch", [ctx.sku_a, second], request_key="batch-request"
        )
        assert replay["batch_id"] == created["batch_id"]
    ids = [task["task_id"] for task in created["tasks"]]
    await asyncio.gather(
        worker(ctx).run_one(ctx.a, ids[0]),
        worker(ctx, AsyncMock(return_value={"is_passed": False})).run_one(
            ctx.a, ids[1]
        ),
    )
    async with ctx.sessions() as session:
        detail = await BatchService(session).get_batch_detail(
            ctx.a, created["batch_id"]
        )
        assert detail["batch"]["status"] == "failed"
        assert (
            detail["batch"]["completed_count"] == detail["batch"]["failed_count"] == 1
        )
        await TaskService(session).retrigger_task(ctx.a, ids[1])
        detail = await BatchService(session).get_batch_detail(
            ctx.a, created["batch_id"]
        )
        assert (
            detail["batch"]["status"] == "pending"
            and detail["batch"]["failed_count"] == 0
        )


async def test_disabled_tenant_does_not_start_queued_models(queue_db):
    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    async with ctx.sessions() as session:
        tenant = await session.get(Tenant, ctx.a)
        tenant.status = "disabled"
        await session.commit()
    runner = AsyncMock()
    assert not await worker(ctx, runner).run_one(ctx.a, task_id)
    task, attempt = await task_and_execution(ctx, task_id)
    assert task.status == attempt.status == "failed"
    runner.assert_not_awaited()


async def test_task_and_batch_api_persist_without_running_background_models(queue_db):
    from app.core.deps import get_current_user_and_tenant, get_db
    from main import app

    ctx = queue_db

    async def database():
        async with ctx.sessions() as session:
            yield session

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user_and_tenant] = lambda: {
        "tenant_id": ctx.a,
        "user_id": None,
    }
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            headers = {"Idempotency-Key": "api-task"}
            one = await client.post(
                "/api/v1/tasks", headers=headers, json={"sku_id": ctx.sku_a}
            )
            two = await client.post(
                "/api/v1/tasks", headers=headers, json={"sku_id": ctx.sku_a}
            )
            assert one.status_code == two.status_code == 200
            assert one.json()["data"]["status"] == "pending"
            task_id = one.json()["data"]["task_id"]
            assert task_id == two.json()["data"]["task_id"]
            assert (
                await client.post(f"/api/v1/tasks/{task_id}/run")
            ).status_code == 409
            other = await client.post("/api/v1/tasks", json={"sku_id": ctx.sku_b})
            assert other.status_code == 404
            batch = await client.post(
                "/api/v1/batches",
                headers={"Idempotency-Key": "api-batch"},
                json={"name": "API batch", "sku_ids": [ctx.sku_a]},
            )
            assert batch.status_code == 200
            _, attempt = await task_and_execution(ctx, task_id)
            assert attempt.status == "pending" and attempt.started_at is None
            stopped = await client.post(f"/api/v1/tasks/{task_id}/cancel", json={"execution_id": attempt.id})
            assert stopped.status_code == 200 and stopped.json()["data"]["status"] == "canceled"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("max_retries", [0, 1, 2])
async def test_review_retry_limit_counts_additional_rounds(monkeypatch, max_retries):
    from app.agent import graph
    from app.agent.nodes import quality_reviewer

    copy_node = AsyncMock(return_value={"creative_plan": {"title": "Ceramic mug"}})
    llm = AsyncMock()
    llm.chat_completion.return_value = {
        "content": '{"score":70,"passed":0,"violations":["Needs revision"],"suggestions":[]}'
    }
    monkeypatch.setattr(
        quality_reviewer.ProviderFactory, "get_llm_client", lambda *args: llm
    )
    monkeypatch.setattr(quality_reviewer, "record_node_execution", AsyncMock())
    monkeypatch.setattr(graph, "orchestrator_node", AsyncMock(return_value={}))
    monkeypatch.setattr(graph, "requirement_analyzer_node", AsyncMock(return_value={}))
    monkeypatch.setattr(graph, "creative_planner_node", copy_node)
    monkeypatch.setattr(graph, "visual_designer_node", AsyncMock(return_value={}))
    monkeypatch.setattr(graph, "image_generator_node", AsyncMock(return_value={}))
    monkeypatch.setattr(graph, "video_generator_node", AsyncMock(return_value={}))
    result = (
        await graph.build_workflow()
        .compile()
        .ainvoke({"max_retries": max_retries, "retry_count": 0})
    )
    assert copy_node.await_count == llm.chat_completion.await_count == max_retries + 1
    assert result["retry_count"] == max_retries and result["is_passed"] is False


async def test_worker_concurrency_limit_and_recovery_loop(queue_db, monkeypatch):
    ctx = queue_db
    monkeypatch.setattr(settings, "TASK_WORKER_POLL_SECONDS", 0.1)
    ids = [(await create(ctx))["task_id"] for _ in range(3)]
    entered, release = asyncio.Event(), asyncio.Event()
    active, peak, count = 0, 0, 0

    async def runner(**kwargs):
        nonlocal active, peak, count
        active += 1
        peak = max(peak, active)
        count += 1
        if count == 2:
            entered.set()
        await release.wait()
        active -= 1
        return {"is_passed": True}

    current = worker(ctx, runner, concurrency=2)
    await current.start()
    try:
        await asyncio.wait_for(entered.wait(), 8)
        await asyncio.sleep(0.3)
        assert count == peak == 2
        release.set()
        async with asyncio.timeout(8):
            while True:
                async with ctx.sessions() as session:
                    complete = await session.scalar(
                        select(func.count())
                        .select_from(Task)
                        .where(
                            Task.tenant_id == ctx.a,
                            Task.id.in_(ids),
                            Task.status == "completed",
                        )
                    )
                if complete == 3:
                    break
                await asyncio.sleep(0.1)
        assert count == 3 and peak == 2
    finally:
        release.set()
        await current.stop()


async def test_legacy_running_task_recovers_without_replaying(queue_db):
    ctx = queue_db
    task_id = uuid4().hex
    async with ctx.sessions() as session:
        session.add(
            Task(id=task_id, tenant_id=ctx.a, sku_id=ctx.sku_a, status="running")
        )
        await session.commit()
    runner = AsyncMock()
    assert not await worker(ctx, runner).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        task = await session.get(Task, task_id)
        assert task.status == "failed" and task.error_message == INTERRUPTED
    runner.assert_not_awaited()


async def test_editing_active_copy_is_blocked_and_historical_edits_keep_current_approval(
    queue_db,
):
    from app.services.copy_service import CopyService

    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    await worker(ctx).claim(ctx.a, task_id)
    _, attempt = await task_and_execution(ctx, task_id)
    async with ctx.sessions() as session:
        copy = Copy(
            tenant_id=ctx.a,
            task_id=task_id,
            sku_id=ctx.sku_a,
            execution_id=attempt.id,
            title="Active copy",
        )
        session.add(copy)
        await session.commit()
        with pytest.raises(TaskConflictError):
            await CopyService(session).update_copy(
                ctx.a, copy.id, {"title": "Unsafe concurrent edit"}
            )
    await worker(ctx).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        await TaskService(session).retrigger_task(ctx.a, task_id)
    assert await worker(ctx).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        await CopyService(session).update_copy(
            ctx.a, copy.id, {"title": "Edit historical copy"}
        )
        task = (
            await session.execute(
                select(Task).where(Task.id == task_id, Task.tenant_id == ctx.a)
            )
        ).scalar_one()
        assert task.status == "completed"


async def test_durable_worker_runs_full_stub_workflow_and_persists_current_outputs(
    queue_db, monkeypatch
):
    import json

    from app.agent import graph, recorder
    from app.agent.nodes import (
        creative_planner,
        image_generator,
        quality_reviewer,
        video_generator,
    )
    from app.clients import postgres
    from app.clients.provider_factory import KlingVideoClient, ProviderFactory
    from app.services import provider_runtime, task_worker

    ctx = queue_db
    task_id = (await create(ctx))["task_id"]
    draft = {
        "title": "Ceramic Mug",
        "bullets": [f"Verified mug detail {i}" for i in range(5)],
        "description": "A ceramic mug for daily use.",
        "keywords": ["ceramic mug", "mug", "drinkware", "ceramic cup", "daily cup"],
    }
    plan = {
        name: "A ceramic mug on a neutral background."
        for name in (
            "main_image",
            "scene_image",
            "detail_image",
            "video_storyboard",
        )
    }
    llm, images = AsyncMock(), AsyncMock()
    video = KlingVideoClient(api_key="offline-video-key", model="wan3.0-video")
    video.submit_video = AsyncMock(
        return_value={"task_id": "offline-remote-video", "task_status": "PENDING"}
    )
    video.query_video = AsyncMock(
        return_value={
            "task_id": "offline-remote-video",
            "task_status": "SUCCEEDED",
            "video_url": "https://assets.example.test/mug.mp4",
        }
    )
    llm.chat_completion.side_effect = [
        {"content": json.dumps(value), "is_mock": 0, "cost": 0.001}
        for value in (
            draft,
            plan,
            {"score": 95, "passed": 1, "violations": [], "suggestions": []},
        )
    ]
    images.generate_images.return_value = {
        "urls": ["https://assets.example.test/mug.png"],
        "is_mock": 0,
        "cost": 0.002,
    }
    for module in (
        task_worker,
        postgres,
        provider_runtime,
        recorder,
        creative_planner,
        image_generator,
        video_generator,
        quality_reviewer,
    ):
        monkeypatch.setattr(module, "AsyncSessionLocal", ctx.sessions)
    monkeypatch.setattr(ProviderFactory, "get_llm_client", lambda *args: llm)
    monkeypatch.setattr(ProviderFactory, "get_image_client", lambda *args: images)
    monkeypatch.setattr(ProviderFactory, "get_video_client", lambda *args: video)
    monkeypatch.setattr(graph, "requirement_analyzer_node", AsyncMock(return_value={}))
    monkeypatch.setattr(graph, "app_workflow", graph.build_workflow().compile())
    assert await worker(ctx, task_worker.execute_workflow).run_one(ctx.a, task_id)
    async with ctx.sessions() as session:
        detail = await TaskService(session).get_task_detail(ctx.a, task_id)
        nodes = await TaskService(session).get_node_runs(ctx.a, task_id)
        assert detail["task"]["status"] == "completed"
        assert detail["copy"] == draft and len(detail["assets"]) == 4
        assert detail["compliance_report"]["passed"] == 1
        assert all(
            node["execution_id"] == detail["task"]["execution_id"] for node in nodes
        )
        assert len([node for node in nodes if node["status"] == "running"]) == 7
        assert len([node for node in nodes if node["status"] == "success"]) == 6
        assert sum(node["cost"] for node in nodes) == pytest.approx(0.009)
    images.generate_images.assert_awaited()
    video.submit_video.assert_awaited_once()
    video.query_video.assert_awaited_once()
