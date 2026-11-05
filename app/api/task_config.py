"""Bounded generation inputs shared by task and batch endpoints."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TaskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field("en", min_length=2, max_length=16)
    platform: Literal["amazon", "tiktok", "tiktok_shop", "shopify", "temu"] = "amazon"
    media_type: Literal["image", "video", "both"] = "both"
    model_llm: str = Field("qwen", max_length=64)
    model_image: str = Field("wanx", max_length=64)
    model_video: str = Field("kling", max_length=64)
    max_retries: int = Field(2, ge=0, le=2, strict=True)
