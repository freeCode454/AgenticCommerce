"""Remote-video wire contracts, restart recovery and billing ambiguity (offline)."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, update
from test_task_queue import create, task_and_execution, worker
from test_task_queue import (
    queue_db as queue_db,  # noqa: PLC0414 -- Re-export the shared pytest fixture.
)

from app.agent.state import AgentState
from app.clients.provider_factory import KlingVideoClient, ProviderFactory
from app.clients.wan_video import (
    RemoteVideoPending,
    SubmissionUnknownError,
    VideoProviderError,
    VideoQueryError,
    validate_video_base,
)
from app.conf.config import settings
from app.core.provider_context import ProviderBinding, ProviderSnapshot
from app.core.task_execution import ExecutionContext, active_execution
from app.models import Asset, ProviderJob, TaskNodeRun
from app.models.base import utc_now
from app.services.remote_video import generate_durable_video
from app.services.workflow_checkpoint import checkpoint_node, save_provider_snapshot


@pytest.fixture
def wire(monkeypatch):
    client = AsyncMock()
    client.__aenter__.return_value = client
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    return client


@pytest.mark.parametrize("http_status", [500, 502, 503, 408])
async def test_ambiguous_submit_never_retries_or_returns_mock(wire, http_status):
    wire.post.return_value = httpx.Response(
        http_status, json={"message": "private-provider-message"}
    )
    client = KlingVideoClient("offline-key")
    with pytest.raises(SubmissionUnknownError) as caught:
        await client.submit_video("Mug")
    assert "private-provider-message" not in str(caught.value)
    wire.post.assert_awaited_once()
    wire.get.assert_not_awaited()


async def test_submit_timeout_is_ambiguous_and_not_retried(wire):
    wire.post.side_effect = httpx.ReadTimeout("private-provider-response")
    with pytest.raises(SubmissionUnknownError):
        await KlingVideoClient("offline-key").submit_video("Mug")
    wire.post.assert_awaited_once()


@pytest.mark.parametrize("status", [401, 403, 429])
async def test_explicit_submit_rejection_cannot_fall_back_to_demo_video(
    wire, monkeypatch, status
):
    from app.clients.provider_factory import ProviderCallError

    monkeypatch.setattr(settings, "ALLOW_MOCK_ASSETS", True)
    wire.post.return_value = httpx.Response(
        status, json={"message": "private-provider-response"}
    )
    with pytest.raises(ProviderCallError) as caught:
        await KlingVideoClient("offline-key").generate_video("Ceramic mug")
    assert "private-provider-response" not in str(caught.value)
    wire.post.assert_awaited_once()
    wire.get.assert_not_awaited()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"output": {}},
        {"output": {"task_id": "../../other-task"}},
        {"output": {"task_id": None}},
    ],
)
async def test_invalid_submission_id_cannot_trigger_resubmit_or_path_injection(
    wire, body
):
    wire.post.return_value = httpx.Response(200, json=body)
    with pytest.raises(SubmissionUnknownError):
        await KlingVideoClient("offline-key").submit_video("Mug")
    wire.post.assert_awaited_once()
    wire.get.assert_not_awaited()


async def test_current_wan_wire_contract_has_media_and_requested_ratio(wire):
    wire.post.return_value = httpx.Response(
        200, json={"output": {"task_id": "remote-123", "task_status": "PENDING"}}
    )
    client = KlingVideoClient(
        "offline-key",
        "wan3.0-video",
        "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
    )
    result = await client.submit_video(
        "Ceramic mug",
        aspect_ratio="16:9",
        image_url="https://assets.example.test/mug.png",
    )
    assert result["task_id"] == "remote-123"
    request = wire.post.call_args.kwargs
    assert request["json"]["input"]["media"] == [
        {"type": "first_frame", "url": "https://assets.example.test/mug.png"}
    ]
    assert "image_url" not in request["json"]["input"]
    assert request["json"]["parameters"]["ratio"] == "16:9"
    assert request["headers"]["X-DashScope-Async"] == "enable"


@pytest.mark.parametrize(
    "status", ["PENDING", "RUNNING", "FAILED", "CANCELED", "UNKNOWN"]
)
async def test_query_states_use_only_get(wire, status):
    wire.get.return_value = httpx.Response(
        200, json={"output": {"task_id": "remote-123", "task_status": status}}
    )
    result = await KlingVideoClient("offline-key").query_video("remote-123")
    assert result["task_status"] == status
    wire.post.assert_not_awaited()


async def test_query_preserves_usage_but_does_not_invent_video_price(wire):
    wire.get.return_value = httpx.Response(
        200,
        json={
            "output": {
                "task_status": "SUCCEEDED",
                "video_url": "https://assets.example.test/video.mp4",
            },
            "usage": {"video_duration": 5, "private_message": "do-not-persist"},
        },
    )
    result = await KlingVideoClient("offline-key").query_video("remote-123")
    assert result["cost"] == 0 and result["billing_status"] == "not_reported"
    assert result["usage"] == {"video_duration": 5}
    wire.post.assert_not_awaited()


@pytest.mark.parametrize(
    "body",
    [
        {"output": {"task_status": "SURPRISE"}},
        {"output": {"task_status": "SUCCEEDED", "video_url": "javascript:alert(1)"}},
        {"output": {"task_status": "RUNNING", "task_id": "different-task"}},
    ],
)
async def test_bad_query_response_can_only_retry_the_read(wire, body):
    wire.get.return_value = httpx.Response(200, json=body)
    with pytest.raises(VideoQueryError):
        await KlingVideoClient("offline-key").query_video("remote-123")
    wire.post.assert_not_awaited()


@pytest.mark.parametrize(
    "base",
    [
        "http://dashscope.aliyuncs.com/api/v1",
        "https://evil.test/api/v1",
        "https://dashscope.aliyuncs.com.evil.test/api/v1",
        "https://user:password@dashscope.aliyuncs.com/api/v1",
        "https://dashscope.aliyuncs.com/api/v1?token=x",
    ],
)
def test_api_base_rejects_credential_exfiltration_targets(base):
    with pytest.raises(VideoProviderError):
        validate_video_base(base)


@pytest_asyncio.fixture
async def remote_context(queue_db, monkeypatch):
    ctx = queue_db
    created = await create(ctx)
    task_id = created["task_id"]
    await worker(ctx).claim(ctx.a, task_id)
    _, attempt = await task_and_execution(ctx, task_id)
    context = ExecutionContext(ctx.a, task_id, attempt.id)
    state: AgentState = {
        "task_id": task_id,
        "tenant_id": ctx.a,
        "sku_id": ctx.sku_a,
        "sku_data": {"name": "Ceramic mug"},
        "config": {"max_retries": 0},
        "retry_count": 0,
        "max_retries": 0,
        "completed_steps": [],
        "creative_plan": {"title": "Ceramic mug"},
        "generation_prompts": {
            key: "A ceramic mug on a plain background."
            for key in ("main_image", "scene_image", "detail_image", "video_storyboard")
        },
        "generated_images": [
            {"url": "https://assets.example.test/mug.png", "is_mock": 0}
        ],
    }
    token = active_execution.set(context)
    try:
        await save_provider_snapshot(
            ProviderSnapshot(
                ctx.a,
                (
                    (
                        "video",
                        ProviderBinding(
                            "", "wan3.0-video", "offline-original-video-key"
                        ),
                    ),
                ),
            )
        )
        await checkpoint_node("video_generator", state)
        yield ctx, context, state
    finally:
        active_execution.reset(token)


def fake_video(monkeypatch, query=None, submit=None):
    client = KlingVideoClient("offline-original-video-key", "wan3.0-video")
    client.submit_video = submit or AsyncMock(
        return_value={"task_id": "remote-recovery-123", "task_status": "PENDING"}
    )
    client.query_video = query or AsyncMock(
        return_value={"task_id": "remote-recovery-123", "task_status": "RUNNING"}
    )
    monkeypatch.setattr(ProviderFactory, "get_video_client", lambda *args: client)
    return client


async def submit_pending(context, client):
    ctx, identity, state = context
    with pytest.raises(RemoteVideoPending):
        await generate_durable_video(
            client,
            prompt=state["generation_prompts"]["video_storyboard"],
            duration=5,
            aspect_ratio="16:9",
            image_url=state["generated_images"][0]["url"],
            round_number=0,
        )
    return (await task_and_execution(ctx, identity.task_id))[1]


async def test_remote_id_and_ciphertext_are_committed_before_first_query(
    remote_context, monkeypatch
):
    ctx, identity, _ = remote_context

    async def query(remote_id):
        async with ctx.sessions() as session:
            job = (
                await session.execute(
                    select(ProviderJob).where(
                        ProviderJob.tenant_id == ctx.a,
                        ProviderJob.execution_id == identity.execution_id,
                    )
                )
            ).scalar_one()
            assert job.remote_id == remote_id
            assert job.api_key_enc.startswith("enc:v1:")
            assert "offline-original-video-key" not in job.api_key_enc
        return {"task_status": "RUNNING", "task_id": remote_id}

    client = fake_video(monkeypatch, query=AsyncMock(side_effect=query))
    await submit_pending(remote_context, client)
    client.submit_video.assert_awaited_once()


async def test_unstarted_review_resumes_without_generating_copy_images_or_video(
    remote_context, monkeypatch
):
    from app.agent import graph, recorder
    from app.services.task_worker import execute_workflow

    ctx, identity, state = remote_context
    client = fake_video(
        monkeypatch,
        query=AsyncMock(
            return_value={
                "task_status": "SUCCEEDED",
                "video_url": "https://assets.example.test/video.mp4",
            }
        ),
    )
    result = await generate_durable_video(
        client,
        prompt=state["generation_prompts"]["video_storyboard"],
        duration=5,
        aspect_ratio="16:9",
        image_url=state["generated_images"][0]["url"],
        round_number=0,
    )
    await checkpoint_node(
        "video_generator",
        state,
        {
            "generated_video": result,
            "current_step": "video_generator",
            "completed_steps": ["video_generator"],
        },
    )
    original_llm_key = settings.DASHSCOPE_API_KEY
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "changed-global-key")
    forbidden = AsyncMock(
        side_effect=AssertionError("Completed generation must not run again")
    )
    for name in (
        "orchestrator_node",
        "requirement_analyzer_node",
        "creative_planner_node",
        "visual_designer_node",
        "image_generator_node",
        "video_generator_node",
    ):
        monkeypatch.setattr(graph, name, forbidden)

    async def review(state):
        assert ProviderFactory.get_llm_client().api_key == original_llm_key
        return {
            "is_passed": True,
            "should_retry": False,
            "current_step": "quality_reviewer",
        }

    reviewer = AsyncMock(side_effect=review)
    monkeypatch.setattr(recorder, "AsyncSessionLocal", ctx.sessions)
    monkeypatch.setattr(graph, "quality_reviewer_node", reviewer)
    monkeypatch.setattr(graph, "app_workflow", graph.build_workflow().compile())
    assert await worker(ctx, execute_workflow).run_one(ctx.a, identity.task_id)
    forbidden.assert_not_awaited()
    reviewer.assert_awaited_once()
    client.submit_video.assert_awaited_once()


async def test_restart_queries_original_remote_job_with_frozen_credentials(
    remote_context, monkeypatch
):
    from app.agent import graph, recorder
    from app.agent.nodes import video_generator
    from app.services.task_worker import execute_workflow

    ctx, identity, _ = remote_context
    first_client = fake_video(monkeypatch)
    await submit_pending(remote_context, first_client)
    # No live session lock remains: this is a simulated process restart.
    monkeypatch.setattr(
        settings, "DASHSCOPE_API_KEY", "new-default-key-must-not-be-used"
    )
    monkeypatch.setattr(
        settings,
        "DASHSCOPE_VIDEO_API_BASE",
        "https://new-workspace.cn-beijing.maas.aliyuncs.com/api/v1",
    )
    observed = []

    async def query(self, remote_id):
        observed.append((self.api_key, self.api_base, remote_id))
        return {
            "task_id": remote_id,
            "task_status": "SUCCEEDED",
            "video_url": "https://assets.example.test/recovered.mp4",
        }

    monkeypatch.setattr(KlingVideoClient, "query_video", query)
    forbidden = AsyncMock(side_effect=AssertionError("must not resubmit"))
    monkeypatch.setattr(KlingVideoClient, "submit_video", forbidden)
    for module in (video_generator, recorder):
        monkeypatch.setattr(module, "AsyncSessionLocal", ctx.sessions)
    review = AsyncMock(return_value={"is_passed": True, "should_retry": False})
    monkeypatch.setattr(graph, "quality_reviewer_node", review)
    monkeypatch.setattr(graph, "app_workflow", graph.build_workflow().compile())
    assert await worker(ctx, execute_workflow).run_one(ctx.a, identity.task_id)
    assert observed == [
        (
            "offline-original-video-key",
            "https://dashscope.aliyuncs.com/api/v1",
            "remote-recovery-123",
        )
    ]
    forbidden.assert_not_awaited()
    first_client.submit_video.assert_awaited_once()
    review.assert_awaited_once()
    task, attempt = await task_and_execution(ctx, identity.task_id)
    assert task.status == attempt.status == "completed"
    async with ctx.sessions() as session:
        assets = (
            (await session.execute(select(Asset).where(Asset.tenant_id == ctx.a)))
            .scalars()
            .all()
        )
        assert len(assets) == 1 and assets[0].url.endswith("recovered.mp4")


async def test_waiting_job_releases_worker_slot_and_cannot_be_retriggered(
    remote_context, monkeypatch
):
    from app.services.task_queue import TaskConflictError
    from app.services.task_service import TaskService

    ctx, identity, _ = remote_context
    await submit_pending(remote_context, fake_video(monkeypatch))
    await worker(ctx).finish(identity, "waiting")
    task, attempt = await task_and_execution(ctx, identity.task_id)
    assert task.status == "running" and attempt.status == "pending"
    assert attempt.next_poll_at > utc_now()
    assert await worker(ctx).claim(ctx.a, identity.task_id) is None
    async with ctx.sessions() as session:
        with pytest.raises(TaskConflictError):
            await TaskService(session).retrigger_task(ctx.a, identity.task_id)


async def test_submission_timeout_is_not_recoverable_and_is_never_reposted(
    remote_context, monkeypatch
):
    ctx, identity, state = remote_context
    client = fake_video(
        monkeypatch,
        submit=AsyncMock(side_effect=SubmissionUnknownError("提交结果不明")),
    )
    payload = {
        "prompt": state["generation_prompts"]["video_storyboard"],
        "duration": 5,
        "aspect_ratio": "16:9",
        "image_url": state["generated_images"][0]["url"],
        "round_number": 0,
    }
    with pytest.raises(SubmissionUnknownError):
        await generate_durable_video(client, **payload)
    with pytest.raises(SubmissionUnknownError):
        await generate_durable_video(client, **payload)
    client.submit_video.assert_awaited_once()
    called = AsyncMock()
    assert not await worker(ctx, called).run_one(ctx.a, identity.task_id)
    task, attempt = await task_and_execution(ctx, identity.task_id)
    assert task.status == "failed" and attempt.status == "interrupted"
    called.assert_not_awaited()


async def test_interrupted_review_cannot_be_replayed_even_with_successful_video(
    remote_context, monkeypatch
):
    ctx, identity, state = remote_context
    client = fake_video(
        monkeypatch,
        query=AsyncMock(
            return_value={
                "task_status": "SUCCEEDED",
                "video_url": "https://assets.example.test/video.mp4",
            }
        ),
    )
    result = await generate_durable_video(
        client,
        prompt=state["generation_prompts"]["video_storyboard"],
        duration=5,
        aspect_ratio="16:9",
        image_url=state["generated_images"][0]["url"],
        round_number=0,
    )
    state["generated_video"] = result
    await checkpoint_node("quality_reviewer", state)
    called = AsyncMock()
    assert not await worker(ctx, called).run_one(ctx.a, identity.task_id)
    _, attempt = await task_and_execution(ctx, identity.task_id)
    assert attempt.status == "interrupted"
    called.assert_not_awaited()


async def test_expired_remote_id_fails_without_query_or_new_submission(
    remote_context, monkeypatch
):
    ctx, identity, state = remote_context
    first = fake_video(monkeypatch)
    await submit_pending(remote_context, first)
    async with ctx.sessions() as session:
        await session.execute(
            update(ProviderJob)
            .where(
                ProviderJob.tenant_id == ctx.a,
                ProviderJob.execution_id == identity.execution_id,
            )
            .values(expires_at=utc_now() - timedelta(seconds=1))
        )
        await session.commit()
    posted, queried = AsyncMock(), AsyncMock()
    monkeypatch.setattr(KlingVideoClient, "submit_video", posted)
    monkeypatch.setattr(KlingVideoClient, "query_video", queried)
    with pytest.raises(VideoProviderError):
        await generate_durable_video(
            prompt=state["generation_prompts"]["video_storyboard"],
            duration=5,
            aspect_ratio="16:9",
            image_url=state["generated_images"][0]["url"],
            round_number=0,
        )
    posted.assert_not_awaited()
    queried.assert_not_awaited()


async def test_query_failure_keeps_remote_id_and_uses_persisted_backoff(
    remote_context, monkeypatch
):
    ctx, identity, _ = remote_context
    client = fake_video(
        monkeypatch,
        query=AsyncMock(side_effect=VideoQueryError("查询暂时失败，未重新提交。")),
    )
    await submit_pending(remote_context, client)
    await worker(ctx).finish(identity, "waiting")
    _, attempt = await task_and_execution(ctx, identity.task_id)
    assert attempt.status == "pending" and attempt.next_poll_at > utc_now() + timedelta(
        seconds=20
    )
    async with ctx.sessions() as session:
        job = (
            await session.execute(
                select(ProviderJob).where(
                    ProviderJob.tenant_id == ctx.a,
                    ProviderJob.execution_id == identity.execution_id,
                )
            )
        ).scalar_one()
        assert job.remote_id == "remote-recovery-123" and job.query_failures == 1
        assert job.error_message
    client.submit_video.assert_awaited_once()


async def test_success_replay_deduplicates_asset_and_node_record(
    remote_context, monkeypatch
):
    from app.agent import recorder
    from app.agent.nodes import video_generator

    ctx, _, state = remote_context
    client = fake_video(
        monkeypatch,
        query=AsyncMock(
            return_value={
                "task_status": "SUCCEEDED",
                "video_url": "https://assets.example.test/video.mp4",
            }
        ),
    )
    for module in (video_generator, recorder):
        monkeypatch.setattr(module, "AsyncSessionLocal", ctx.sessions)
    first = await video_generator.video_generator_node(state)
    second = await video_generator.video_generator_node(state)
    assert first == second
    client.submit_video.assert_awaited_once()
    client.query_video.assert_awaited_once()
    async with ctx.sessions() as session:
        assets = (
            (await session.execute(select(Asset).where(Asset.tenant_id == ctx.a)))
            .scalars()
            .all()
        )
        records = (
            (
                await session.execute(
                    select(TaskNodeRun).where(TaskNodeRun.tenant_id == ctx.a)
                )
            )
            .scalars()
            .all()
        )
        assert len(assets) == len(records) == 1
        assert records[0].provider_job_id == assets[0].provider_job_id
        assert (
            records[0].cost == 0 and assets[0].meta["billing_status"] == "not_reported"
        )


async def test_shutdown_during_query_preserves_recoverable_job(
    remote_context, monkeypatch
):
    ctx, identity, state = remote_context
    await submit_pending(remote_context, fake_video(monkeypatch))
    entered = asyncio.Event()

    async def query(self, remote_id):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(KlingVideoClient, "query_video", query)
    forbidden = AsyncMock()
    monkeypatch.setattr(KlingVideoClient, "submit_video", forbidden)

    async def runner(**kwargs):
        await generate_durable_video(
            prompt=state["generation_prompts"]["video_storyboard"],
            duration=5,
            aspect_ratio="16:9",
            image_url=state["generated_images"][0]["url"],
            round_number=0,
        )

    current = worker(ctx, runner)
    job = asyncio.create_task(current.run_one(ctx.a, identity.task_id))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        task, attempt = await task_and_execution(ctx, identity.task_id)
        assert task.status == "running" and attempt.status == "pending"
        assert await current.claim(ctx.a, identity.task_id)
    finally:
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
    forbidden.assert_not_awaited()


async def test_missing_encryption_key_stops_before_submit(remote_context, monkeypatch):
    from app.core.provider_keys import ProviderConfigurationError

    _, _, state = remote_context
    client = fake_video(monkeypatch)
    monkeypatch.setattr(settings, "PROVIDER_ENCRYPTION_KEY", "")
    with pytest.raises(ProviderConfigurationError):
        await generate_durable_video(
            client,
            prompt=state["generation_prompts"]["video_storyboard"],
            duration=5,
            aspect_ratio="16:9",
            image_url=state["generated_images"][0]["url"],
            round_number=0,
        )
    client.submit_video.assert_not_awaited()
    client.query_video.assert_not_awaited()


async def test_job_detail_does_not_expose_frozen_credentials_or_raw_snapshots(
    remote_context, monkeypatch
):
    from app.services.task_service import TaskService

    ctx, identity, _ = remote_context
    await submit_pending(remote_context, fake_video(monkeypatch))
    async with ctx.sessions() as session:
        detail = await TaskService(session).get_task_detail(ctx.a, identity.task_id)
        text = str(detail)
        assert "offline-original-video-key" not in text
        assert (
            "api_key_enc" not in text
            and "provider_snapshot_enc" not in text
            and "state_snapshot" not in text
        )
        assert detail["remote_jobs"][0]["remote_id"] == "remote-recovery-123"
        with pytest.raises(ValueError):
            await TaskService(session).get_task_detail(ctx.b, identity.task_id)


async def test_changed_restore_prompt_cannot_create_or_query_another_job(
    remote_context, monkeypatch
):
    _, _, state = remote_context
    client = fake_video(monkeypatch)
    await submit_pending(remote_context, client)
    posted, queried = AsyncMock(), AsyncMock()
    monkeypatch.setattr(KlingVideoClient, "submit_video", posted)
    monkeypatch.setattr(KlingVideoClient, "query_video", queried)
    with pytest.raises(VideoProviderError):
        await generate_durable_video(
            prompt="Different paid request",
            duration=5,
            aspect_ratio="16:9",
            image_url=state["generated_images"][0]["url"],
            round_number=0,
        )
    posted.assert_not_awaited()
    queried.assert_not_awaited()


async def test_crash_during_post_is_marked_unknown_and_never_resubmitted(
    remote_context, monkeypatch
):
    ctx, identity, state = remote_context
    entered = asyncio.Event()

    async def post(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    client = fake_video(monkeypatch, submit=AsyncMock(side_effect=post))
    submission = asyncio.create_task(
        generate_durable_video(
            client,
            prompt=state["generation_prompts"]["video_storyboard"],
            duration=5,
            aspect_ratio="16:9",
            image_url=state["generated_images"][0]["url"],
            round_number=0,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        submission.cancel()
        await asyncio.gather(submission, return_exceptions=True)
        runner = AsyncMock()
        assert not await worker(ctx, runner).run_one(ctx.a, identity.task_id)
        runner.assert_not_awaited()
        async with ctx.sessions() as session:
            job = (
                await session.execute(
                    select(ProviderJob).where(
                        ProviderJob.tenant_id == ctx.a,
                        ProviderJob.execution_id == identity.execution_id,
                    )
                )
            ).scalar_one()
            assert job.status == "submission_unknown" and job.remote_id is None
            assert "未重新提交" in job.error_message
    finally:
        submission.cancel()
        await asyncio.gather(submission, return_exceptions=True)
    client.submit_video.assert_awaited_once()
