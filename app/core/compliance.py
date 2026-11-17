"""Shared deterministic checks and fail-closed model review parsing."""

import json
from typing import Any

from pydantic import BaseModel, Field, StrictInt, field_validator

FORBIDDEN_WORDS = ("世界第一", "绝对有效", "100% cure", "best in the world", "cheapest")
REVIEW_UNAVAILABLE = "审核服务不可用或返回格式无效"
REVIEW_DIMENSIONS = ("brand_consistency", "platform_compliance", "readability")


def review_response_format(*, strict: bool) -> dict:
    if not strict:
        return {"type": "json_object"}
    score = {"type": "number", "minimum": 0, "maximum": 100}
    messages = {"type": "array", "items": {"type": "string"}}
    properties = {
        "score": score,
        "passed": {"type": "integer", "enum": [0, 1]},
        "dimensions": {
            "type": "object",
            "properties": {name: score for name in REVIEW_DIMENSIONS},
            "required": list(REVIEW_DIMENSIONS),
            "additionalProperties": False,
        },
        "violations": messages,
        "suggestions": messages,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "copy_review",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


class ReviewResult(BaseModel):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    passed: StrictInt = Field(ge=0, le=1)
    dimensions: dict[str, float] = Field(default_factory=dict)
    violations: list[str | dict[str, Any]]
    suggestions: list[str]

    @field_validator("passed", mode="before")
    @classmethod
    def normalize_boolean_verdict(cls, value: object) -> object:
        return int(value) if isinstance(value, bool) else value


def rule_violations(text: str) -> list[str]:
    return [f"发现敏感绝对化用词: {word}" for word in FORBIDDEN_WORDS if word.casefold() in text.casefold()]


def parse_review(content: str) -> ReviewResult:
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return ReviewResult.model_validate(json.loads(content))
