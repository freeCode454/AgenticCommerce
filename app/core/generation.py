"""Validated generation outputs; malformed responses never become product content."""

import json
import re
from typing import Annotated, Any, NoReturn

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Bullet = Annotated[Text, Field(max_length=2000)]
Keyword = Annotated[Text, Field(max_length=200)]
Prompt = Annotated[Text, Field(max_length=6000)]


class GenerationOutputError(ValueError):
    """An actionable error without raw model output or provider credentials."""

    def __init__(self, code: str = "invalid_generation_output") -> None:
        self.code = code
        messages = {
            "invalid_generation_output": "模型返回内容不符合生成结构，已停止后续生成，请重试。",
            "mock_generation_output": "生成节点返回模拟内容，已停止后续生成，请检查真实模型配置。",
            "insufficient_product_data": "商品资料不足，请补充真实描述或规格后重新生成。",
        }
        super().__init__(messages[code])


class GenerationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class CopyDraft(GenerationModel):
    title: Annotated[Text, Field(max_length=512)]
    bullets: list[Bullet] = Field(min_length=5, max_length=5)
    description: Annotated[Text, Field(max_length=16000)]
    keywords: list[Keyword] = Field(min_length=5, max_length=8)


class VisualPlan(GenerationModel):
    main_image: Prompt
    scene_image: Prompt
    detail_image: Prompt
    video_storyboard: Prompt


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise ValueError("Non-finite JSON constant")


def parse_generation[Output: GenerationModel](
    response: dict[str, Any], output_type: type[Output]
) -> Output:
    """Accept a JSON object or one JSON fence; reject prose, coercion and mocks."""
    if response.get("is_mock"):
        raise GenerationOutputError("mock_generation_output")
    content = response.get("content")
    if not isinstance(content, str) or len(content) > 100000:
        raise GenerationOutputError()
    content = content.strip()
    fence = re.fullmatch(
        r"```(?:json)?\s*\n([\s\S]*?)\n```", content, flags=re.IGNORECASE
    )
    if fence:
        content = fence.group(1).strip()
    try:
        data = json.loads(
            content, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if isinstance(data, dict) and data == {"error": "insufficient_product_data"}:
            raise GenerationOutputError("insufficient_product_data")
        return output_type.model_validate(data)
    except GenerationOutputError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise GenerationOutputError() from None


def require_visual_plan(prompts: dict[str, Any]) -> VisualPlan:
    """Guard paid media calls, including direct node invocations."""
    try:
        return VisualPlan.model_validate(prompts)
    except ValidationError:
        raise GenerationOutputError() from None


def product_context(sku: dict[str, Any]) -> dict[str, Any]:
    """Only the supplied SKU is a source of factual product attributes."""
    if not isinstance(sku.get("name"), str) or not sku["name"].strip():
        raise GenerationOutputError("insufficient_product_data")
    return {
        key: sku.get(key)
        for key in ("code", "name", "category", "description", "specs", "images")
    }
