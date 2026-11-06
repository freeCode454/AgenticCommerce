"""Single-request Wan transport. Submission is never retried implicitly."""

import math
import re
from urllib.parse import urlsplit

import httpx

from app.conf.config import settings
from app.core.task_execution import guard_model_request


class VideoProviderError(RuntimeError):
    """Sanitized remote-video error, safe to show without provider response bodies."""


class SubmissionUnknownError(VideoProviderError):
    """The provider may have accepted the POST; never automatically submit again."""


class VideoQueryError(VideoProviderError):
    """A read can safely be retried without creating another remote task."""


class RemoteVideoPending(Exception):
    """Yield the worker slot until the persisted poll is due."""


def validate_video_base(value: str) -> str:
    url = urlsplit(value)
    host = url.hostname or ""
    if (
        url.scheme != "https"
        or url.username
        or url.password
        or url.port not in (None, 443)
        or url.query
        or url.fragment
        or url.path.rstrip("/") != "/api/v1"
        or not (host == "dashscope.aliyuncs.com" or host.endswith(".maas.aliyuncs.com"))
    ):
        raise VideoProviderError(
            "视频接口地址无效，请配置同地域的阿里云 HTTPS /api/v1 地址。"
        )
    return value.rstrip("/")


def valid_remote_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise SubmissionUnknownError(
            "无法确认视频提交结果，未再次提交；请核对厂商任务和费用。"
        )
    return value


class WanVideoTransport:
    def __init__(
        self, api_key: str, model: str | None = None, api_base: str | None = None
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = validate_video_base(
            api_base or settings.DASHSCOPE_VIDEO_API_BASE
        )

    async def submit_video(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        model: str = "wan3.0-video",
        image_url: str | None = None,
    ) -> dict:
        await guard_model_request()
        if not self.api_key:
            raise VideoProviderError("视频模型凭据缺失，未提交生成。")
        payload = {
            "model": self.model or model,
            "input": {"prompt": prompt},
            "parameters": {
                "resolution": "480P",
                "ratio": aspect_ratio,
                "duration": duration,
            },
        }
        if image_url:
            payload["input"]["media"] = [{"type": "first_frame", "url": image_url}]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_base + "/services/aigc/video-generation/video-synthesis",
                    headers={
                        "Authorization": "Bearer " + self.api_key,
                        "X-DashScope-Async": "enable",
                    },
                    json=payload,
                )
        except httpx.RequestError:
            raise SubmissionUnknownError(
                "视频提交连接中断，厂商可能已受理；未再次提交，请核对远端任务。"
            ) from None
        if response.status_code >= 500 or response.status_code in (408, 409):
            raise SubmissionUnknownError(
                "无法确认视频提交结果，未再次提交；请核对厂商任务和费用。"
            )
        if response.status_code not in (200, 201, 202):
            raise VideoProviderError(
                f"视频提交被拒绝（HTTP {response.status_code}），请检查模型、地域和凭据。"
            )
        try:
            data = response.json()
            output = data["output"]
            return {
                "task_id": valid_remote_id(output["task_id"]),
                "task_status": output.get("task_status", "PENDING"),
            }
        except (ValueError, TypeError, KeyError):
            raise SubmissionUnknownError(
                "视频提交响应无有效任务 ID，未再次提交；请核对厂商任务。"
            ) from None

    async def query_video(self, remote_id: str) -> dict:
        # Read-only query. The durable caller still fences the current execution.
        remote_id = valid_remote_id(remote_id)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.api_base + "/tasks/" + remote_id,
                    headers={"Authorization": "Bearer " + self.api_key},
                )
        except httpx.RequestError:
            raise VideoQueryError(
                "视频状态查询连接中断，将稍后继续查询，不会重新提交。"
            ) from None
        if response.status_code == 404:
            return {"task_id": remote_id, "task_status": "UNKNOWN"}
        if response.status_code != 200:
            raise VideoQueryError(
                f"视频状态暂不可查（HTTP {response.status_code}），未重新提交。"
            )
        try:
            data = response.json()
            output = data["output"]
            status = output["task_status"]
            if status not in (
                "PENDING",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELED",
                "UNKNOWN",
            ):
                raise ValueError()
            returned_id = output.get("task_id", remote_id)
            if returned_id != remote_id:
                raise ValueError()
            result = {"task_id": remote_id, "task_status": status}
            if status == "SUCCEEDED":
                url = output["video_url"]
                parsed = urlsplit(url) if isinstance(url, str) else None
                if (
                    parsed is None
                    or parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or len(url) > 8192
                ):
                    raise ValueError()
                result.update(
                    video_url=url,
                    usage={key: value for key, value in (data.get("usage") or {}).items()
                           if key in ("video_duration", "input_video_duration", "output_video_duration", "video_count")
                           and type(value) in (int, float) and math.isfinite(value) and value >= 0},
                    cost=0.0,
                    is_mock=0,
                    model=self.model,
                    billing_status="not_reported",
                )
            return result
        except (ValueError, TypeError, KeyError, AttributeError):
            raise VideoQueryError(
                "视频状态响应无效，将继续查询，不会重新提交。"
            ) from None
