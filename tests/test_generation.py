"""Offline generation contract tests. No provider calls or business DB writes."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agent.nodes import (
    creative_planner,
    image_generator,
    requirement_analyzer,
    video_generator,
    visual_designer,
)
from app.core.generation import (
    CopyDraft,
    GenerationOutputError,
    VisualPlan,
    parse_generation,
)


def copy_output(name: str = "Ceramic Mug") -> dict:
    return {
        "title": f"{name} for Everyday Use",
        "bullets": [
            f"[PRODUCT] Discover the {name}.",
            f"[MATERIAL] {name} made from the supplied material.",
            f"[DESIGN] Explore the described {name} design.",
            f"[USE] Use the {name} as described in the product information.",
            f"[DETAILS] Review the supplied {name} specifications.",
        ],
        "description": f"Discover the {name} described in the product information.",
        "keywords": [
            name,
            f"everyday {name}",
            f"{name} design",
            f"{name} details",
            f"{name} product",
        ],
    }


def visual_output(name: str = "Ceramic Mug") -> dict:
    return {
        "main_image": f"Studio photography of the {name} on a white background.",
        "scene_image": f"The {name} in its documented use context.",
        "detail_image": f"Close-up of the documented {name} material and design.",
        "video_storyboard": f"A 5-second 16:9 product view of the {name} with a slow camera pan.",
    }


def response(data: dict, **extra) -> dict:
    return {
        "content": json.dumps(data),
        "is_mock": 0,
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "cost": 0.002,
        **extra,
    }


@pytest.mark.parametrize("has_knowledge", [False, True])
async def test_requirement_analysis_calls_embedding_only_for_searchable_knowledge(monkeypatch, has_knowledge):
    client = Mock(embedding_model="offline-vector-model")
    client.get_embedding = AsyncMock(return_value=[0.01] * 1024)
    client.chat_completion = AsyncMock(return_value={"content": "Audience analysis"})
    repo = Mock()
    repo.has_searchable_chunks = AsyncMock(return_value=has_knowledge)
    repo.search_vectors = AsyncMock(return_value=[SimpleNamespace(content="Verified brand guidance")])

    @asynccontextmanager
    async def session():
        yield object()

    monkeypatch.setattr(requirement_analyzer, "AsyncSessionLocal", session)
    monkeypatch.setattr(requirement_analyzer, "KnowledgeRepository", lambda db: repo)
    monkeypatch.setattr(requirement_analyzer.ProviderFactory, "get_llm_client", lambda *args: client)
    monkeypatch.setattr(requirement_analyzer, "record_node_execution", AsyncMock())
    result = await requirement_analyzer.requirement_analyzer_node({
        "tenant_id": "tenant-a", "sku_data": {"name": "Ceramic mug", "category": "home"},
    })
    repo.has_searchable_chunks.assert_awaited_once_with("tenant-a", "offline-vector-model")
    assert result["requirement_report"]["rag_source_count"] == int(has_knowledge)
    client.chat_completion.assert_awaited_once()
    if has_knowledge:
        client.get_embedding.assert_awaited_once_with("home Ceramic mug")
        assert repo.search_vectors.await_args.kwargs["tenant_id"] == "tenant-a"
        assert "Verified brand guidance" in client.chat_completion.await_args.args[0][-1]["content"]
    else:
        client.get_embedding.assert_not_awaited()
        repo.search_vectors.assert_not_awaited()


@pytest.mark.parametrize("fenced", [False, True])
def test_valid_copy_json_and_single_json_fence(fenced):
    result = response(copy_output())
    if fenced:
        result["content"] = "```json\n" + result["content"] + "\n```"
    assert parse_generation(result, CopyDraft).model_dump() == copy_output()


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"title": 42},
        {"title": "x" * 513},
        {"bullets": ["Only one benefit"]},
        {"bullets": ["valid"] * 4 + [""]},
        {"bullets": "Five bullets"},
        {"keywords": ["only one"]},
        {"keywords": ["one", "two", "three", "four", 5]},
        {"description": None},
        {"unexpected": "must not be silently accepted"},
    ],
)
def test_invalid_copy_shape_is_rejected(changes):
    with pytest.raises(GenerationOutputError):
        parse_generation(response({**copy_output(), **changes}), CopyDraft)


@pytest.mark.parametrize(
    "content",
    [
        "Not JSON",
        "[]",
        "null",
        "{}",
        '{"title":"first","title":"second"}',
        '{"title":NaN}',
        'Explanation before {"title":"Draft"}',
        "```json\n{}\n```\nExtra commentary",
        pytest.param("x" * 100001, id="oversized_output"),
    ],
)
def test_invalid_or_ambiguous_json_has_sanitized_error(content):
    with pytest.raises(GenerationOutputError) as error:
        parse_generation({"content": content}, CopyDraft)
    assert str(error.value) == "模型返回内容不符合生成结构，已停止后续生成，请重试。"


def test_mock_and_insufficient_product_data_cannot_become_success():
    with pytest.raises(GenerationOutputError) as mocked:
        parse_generation(response(copy_output(), is_mock=1), CopyDraft)
    assert mocked.value.code == "mock_generation_output"
    with pytest.raises(GenerationOutputError) as insufficient:
        parse_generation(response({"error": "insufficient_product_data"}), CopyDraft)
    assert insufficient.value.code == "insufficient_product_data"


@pytest.mark.parametrize("field", list(visual_output()))
def test_each_visual_prompt_must_be_present_and_nonblank(field):
    data = visual_output()
    data[field] = "   "
    with pytest.raises(GenerationOutputError):
        parse_generation(response(data), VisualPlan)


@pytest.mark.parametrize(
    "name,category,specs",
    [
        ("Ceramic Mug", "家居生活", {"材质": "ceramic", "容量": "350 ml"}),
        ("Wireless Headphones", "数码配件", {"连接": "Bluetooth"}),
        ("Portable Tent", "户外运动", {"用途": "camping shelter"}),
    ],
)
async def test_copy_node_uses_exact_model_fields_for_each_category(
    monkeypatch, name, category, specs
):
    llm, recorder = AsyncMock(), AsyncMock()
    output = copy_output(name)
    llm.chat_completion.return_value = response(output)
    monkeypatch.setattr(
        creative_planner.ProviderFactory, "get_llm_client", lambda *args: llm
    )
    monkeypatch.setattr(creative_planner, "record_node_execution", recorder)
    result = await creative_planner.creative_planner_node(
        {
            "sku_data": {
                "name": name,
                "category": category,
                "description": "Supplied actual description",
                "specs": specs,
            },
            "retry_count": 1,
            "quality_reports": [
                {"violations": ["Unsupported claim"], "suggestions": ["Remove it"]}
            ],
        }
    )
    assert {key: result["creative_plan"][key] for key in output} == output
    call = llm.chat_completion.call_args
    context = json.loads(call.args[0][1]["content"])["context"]
    assert context["product_facts"]["specs"] == specs
    assert context["product_facts"]["description"] == "Supplied actual description"
    assert context["review_feedback"]["violations"] == ["Unsupported claim"]
    assert context["target"] == {"platform": "amazon", "language": "en"}
    assert call.kwargs["response_format"] == {"type": "json_object"}
    assert recorder.call_args.kwargs["output_data"]["title"] == output["title"]
    assert recorder.call_args.kwargs["prompt_tokens"] == 12
    llm.chat_completion.assert_awaited_once()


@pytest.mark.parametrize(
    "name", ["Ceramic Mug", "Wireless Headphones", "Portable Tent"]
)
async def test_visual_node_passes_model_prompts_without_category_substitution(
    monkeypatch, name
):
    llm, recorder = AsyncMock(), AsyncMock()
    prompts = visual_output(name)
    llm.chat_completion.return_value = response(prompts)
    monkeypatch.setattr(
        visual_designer.ProviderFactory, "get_llm_client", lambda *args: llm
    )
    monkeypatch.setattr(visual_designer, "record_node_execution", recorder)
    result = await visual_designer.visual_designer_node(
        {
            "sku_data": {
                "name": name,
                "description": "Verified description",
                "specs": {"材质": "verified material"},
            },
            "creative_plan": copy_output(name),
            "retry_count": 1,
            "quality_reports": [{"suggestions": ["Use the actual product scene"]}],
        }
    )
    assert result["generation_prompts"] == prompts
    context = json.loads(llm.chat_completion.call_args.args[0][1]["content"])["context"]
    assert context["product_facts"]["specs"] == {"材质": "verified material"}
    assert context["copywriting"]["title"] == copy_output(name)["title"]
    assert context["review_feedback"]["suggestions"] == ["Use the actual product scene"]
    assert context["media_requirements"]["video_duration_seconds"] == 5
    assert result["visual_design"]["video_duration"] == 5
    assert recorder.call_args.kwargs["output_data"]["prompts"] == prompts


@pytest.mark.parametrize(
    "module,node",
    [
        (creative_planner, "creative_planner_node"),
        (visual_designer, "visual_designer_node"),
    ],
)
@pytest.mark.parametrize("failure", ["invalid", "provider", "mock"])
async def test_failed_generation_is_recorded_and_does_not_write_or_retry(
    monkeypatch, module, node, failure
):
    llm, recorder, database = AsyncMock(), AsyncMock(), Mock()
    if failure == "provider":
        llm.chat_completion.side_effect = RuntimeError("SENSITIVE_PROVIDER_BODY")
    else:
        llm.chat_completion.return_value = {
            "content": "SENSITIVE_INVALID_OUTPUT",
            "is_mock": failure == "mock",
        }
    monkeypatch.setattr(module.ProviderFactory, "get_llm_client", lambda *args: llm)
    monkeypatch.setattr(module, "record_node_execution", recorder)
    if module is creative_planner:
        monkeypatch.setattr(module, "AsyncSessionLocal", database)
    with pytest.raises((GenerationOutputError, RuntimeError)):
        await getattr(module, node)(
            {
                "task_id": "offline-task",
                "sku_id": "offline-sku",
                "tenant_id": "offline-tenant",
                "sku_data": {"name": "Ceramic Mug"},
            }
        )
    database.assert_not_called()
    llm.chat_completion.assert_awaited_once()
    record = recorder.call_args.kwargs
    assert record["status"] == "failed"
    assert record["tenant_id"] == "offline-tenant"
    assert "SENSITIVE" not in json.dumps(record["output_data"])
    assert record["input_data"]["messages"]


@pytest.mark.parametrize(
    "module,node",
    [
        (image_generator, "image_generator_node"),
        (video_generator, "video_generator_node"),
    ],
)
async def test_missing_visual_plan_stops_before_any_paid_media_call(
    monkeypatch, module, node
):
    factory = Mock()
    monkeypatch.setattr(module.ProviderFactory, "get_image_client", factory)
    monkeypatch.setattr(module.ProviderFactory, "get_video_client", factory)
    with pytest.raises(GenerationOutputError):
        await getattr(module, node)(
            {"generation_prompts": {"main_image": "Only one field"}}
        )
    factory.assert_not_called()


async def test_invalid_visual_plan_stops_workflow_before_media_nodes(monkeypatch):
    from app.agent import graph

    llm, image, video = AsyncMock(), AsyncMock(), AsyncMock()
    llm.chat_completion.side_effect = [
        response(copy_output()),
        {"content": "invalid visual plan"},
    ]
    factory = creative_planner.ProviderFactory
    monkeypatch.setattr(
        factory,
        "get_llm_client",
        lambda *args: llm,
    )
    monkeypatch.setattr(factory, "get_image_client", image)
    monkeypatch.setattr(factory, "get_video_client", video)
    monkeypatch.setattr(
        graph,
        "orchestrator_node",
        AsyncMock(return_value={"completed_steps": ["orchestrator"]}),
    )
    monkeypatch.setattr(
        graph,
        "requirement_analyzer_node",
        AsyncMock(
            return_value={
                "requirement_report": {"analysis_text": "Use supplied product facts"}
            }
        ),
    )
    monkeypatch.setattr(creative_planner, "record_node_execution", AsyncMock())
    recorder = AsyncMock()
    monkeypatch.setattr(visual_designer, "record_node_execution", recorder)
    with pytest.raises(GenerationOutputError):
        await (
            graph.build_workflow()
            .compile()
            .ainvoke({"sku_data": {"name": "Ceramic Mug"}})
        )
    image.assert_not_called()
    video.assert_not_called()
    assert llm.chat_completion.await_count == 2
    assert recorder.call_args.kwargs["status"] == "failed"


async def test_valid_plan_reaches_media_and_review_without_prompt_replacement(
    monkeypatch,
):
    from app.agent import graph
    from app.agent.nodes import quality_reviewer

    llm, image, video = AsyncMock(), AsyncMock(), AsyncMock()
    prompts = visual_output("Ceramic Mug")
    llm.chat_completion.side_effect = [
        response(copy_output("Ceramic Mug")),
        response(prompts),
        response(
            {
                "score": 95,
                "passed": 1,
                "dimensions": {},
                "violations": [],
                "suggestions": [],
            }
        ),
    ]
    image.generate_images.return_value = {
        "urls": ["https://assets.example.test/mug.png"],
        "is_mock": 0,
        "model": "offline-image",
    }
    video.generate_video.return_value = {
        "video_url": "https://assets.example.test/mug.mp4",
        "is_mock": 0,
        "duration": 5,
        "model": "offline-video",
    }
    factory = creative_planner.ProviderFactory
    monkeypatch.setattr(factory, "get_llm_client", lambda *args: llm)
    monkeypatch.setattr(factory, "get_image_client", lambda *args: image)
    monkeypatch.setattr(factory, "get_video_client", lambda *args: video)
    monkeypatch.setattr(
        graph,
        "orchestrator_node",
        AsyncMock(return_value={"completed_steps": ["orchestrator"]}),
    )
    monkeypatch.setattr(
        graph,
        "requirement_analyzer_node",
        AsyncMock(
            return_value={
                "requirement_report": {"analysis_text": "Supplied facts only"}
            }
        ),
    )
    for module in [
        creative_planner,
        visual_designer,
        image_generator,
        video_generator,
        quality_reviewer,
    ]:
        monkeypatch.setattr(module, "record_node_execution", AsyncMock())
    result = (
        await graph.build_workflow()
        .compile()
        .ainvoke(
            {"sku_data": {"name": "Ceramic Mug"}, "config": {"media_type": "both"}}
        )
    )
    assert result["is_passed"] is True
    assert result["creative_plan"]["title"] == copy_output()["title"]
    assert [call.kwargs["prompt"] for call in image.generate_images.call_args_list] == [
        prompts[key] for key in ["main_image", "scene_image", "detail_image"]
    ]
    assert (
        video.generate_video.call_args.kwargs["prompt"] == prompts["video_storyboard"]
    )
    assert video.generate_video.call_args.kwargs["duration"] == 5
    assert video.generate_video.call_args.kwargs["aspect_ratio"] == "16:9"
    assert llm.chat_completion.await_count == 3


@pytest.mark.parametrize(
    "module,node",
    [
        (creative_planner, "creative_planner_node"),
        (visual_designer, "visual_designer_node"),
    ],
)
async def test_missing_product_identity_fails_before_model_call(
    monkeypatch, module, node
):
    factory, recorder = Mock(), AsyncMock()
    monkeypatch.setattr(module.ProviderFactory, "get_llm_client", factory)
    monkeypatch.setattr(module, "record_node_execution", recorder)
    with pytest.raises(GenerationOutputError) as error:
        await getattr(module, node)({"sku_data": {"description": "No product name"}})
    assert error.value.code == "insufficient_product_data"
    factory.assert_not_called()
    assert recorder.call_args.kwargs["status"] == "failed"


async def test_copy_persistence_failure_is_not_reported_as_success(monkeypatch):
    llm, recorder, session = AsyncMock(), AsyncMock(), AsyncMock()
    llm.chat_completion.return_value = response(copy_output())
    session.__aenter__.return_value = session
    session.add = Mock()
    session.commit.side_effect = RuntimeError("Database unavailable")
    monkeypatch.setattr(
        creative_planner.ProviderFactory, "get_llm_client", lambda *args: llm
    )
    monkeypatch.setattr(
        creative_planner, "AsyncSessionLocal", Mock(return_value=session)
    )
    monkeypatch.setattr(creative_planner, "record_node_execution", recorder)
    with pytest.raises(RuntimeError, match="Database unavailable"):
        await creative_planner.creative_planner_node(
            {
                "task_id": "offline-task",
                "tenant_id": "offline-tenant",
                "sku_id": "offline-sku",
                "sku_data": {"name": "Ceramic Mug"},
            }
        )
    assert recorder.await_count == 1
    assert recorder.call_args.kwargs["status"] == "failed"


async def test_recorder_failure_preserves_the_original_generation_error(monkeypatch):
    llm = AsyncMock()
    llm.chat_completion.return_value = {"content": "bad output"}
    monkeypatch.setattr(
        creative_planner.ProviderFactory, "get_llm_client", lambda *args: llm
    )
    monkeypatch.setattr(
        creative_planner,
        "record_node_execution",
        AsyncMock(side_effect=RuntimeError("Database unavailable")),
    )
    with pytest.raises(GenerationOutputError):
        await creative_planner.creative_planner_node(
            {"sku_data": {"name": "Ceramic Mug"}}
        )


async def test_review_receives_original_facts_keywords_and_untruncated_description(
    monkeypatch,
):
    from app.agent.nodes import quality_reviewer

    llm = AsyncMock()
    llm.chat_completion.return_value = response(
        {
            "score": 0,
            "passed": 0,
            "violations": ["Unsupported claim"],
            "suggestions": ["Remove unsupported claim"],
        }
    )
    monkeypatch.setattr(
        quality_reviewer.ProviderFactory, "get_llm_client", lambda *args: llm
    )
    monkeypatch.setattr(quality_reviewer, "record_node_execution", AsyncMock())
    description = "Product description " * 30 + "CLAIM_AFTER_CHARACTER_300"
    result = await quality_reviewer.quality_reviewer_node(
        {
            "sku_data": {"name": "Ceramic Mug", "specs": {"capacity": "350 ml"}},
            "creative_plan": {**copy_output(), "description": description},
        }
    )
    prompt = llm.chat_completion.call_args.args[0][1]["content"]
    assert "350 ml" in prompt
    assert "CLAIM_AFTER_CHARACTER_300" in prompt
    assert "everyday Ceramic Mug" in prompt
    assert result["is_passed"] is False
