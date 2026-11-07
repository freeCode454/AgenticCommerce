"""Bounded generation inputs shared by task and batch endpoints."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TaskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en"] = "en"
    platform: Literal["amazon"] = "amazon"
    media_type: Literal["both"] = "both"
    model_llm: Literal["qwen"] = "qwen"
    model_image: Literal["wanx"] = "wanx"
    model_video: Literal["kling"] = "kling"
    max_retries: int = Field(2, ge=0, le=2, strict=True)
