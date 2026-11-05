"""Shared deterministic checks and fail-closed model review parsing."""

import json
from typing import Any

from pydantic import BaseModel, Field, StrictInt

FORBIDDEN_WORDS = ("世界第一", "绝对有效", "100% cure", "best in the world", "cheapest")


class ReviewResult(BaseModel):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    passed: StrictInt = Field(ge=0, le=1)
    dimensions: dict[str, float] = Field(default_factory=dict)
    violations: list[str | dict[str, Any]]
    suggestions: list[str]


def rule_violations(text: str) -> list[str]:
    return [f"发现敏感绝对化用词: {word}" for word in FORBIDDEN_WORDS if word.casefold() in text.casefold()]


def parse_review(content: str) -> ReviewResult:
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return ReviewResult.model_validate(json.loads(content))
