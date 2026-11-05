"""
VideoGenerator Agent (视频生成智能体)
功能：调用快手可灵 Kling AI API，根据分镜脚本生成 5-10 秒产品动态带货短视频，并持久化保存至 ac_asset 表
"""

import time
import logging
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.postgres import AsyncSessionLocal
from app.clients.provider_factory import ProviderFactory
from app.models.asset import Asset
from app.prompt.templates import load_prompt_template

logger = logging.getLogger("video_generator_node")

async def video_generator_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_id = state.get("sku_id") or ""
    prompts = state.get("generation_prompts") or {}
    images = state.get("generated_images") or []

    logger.info(f"视频生成智能体启动: task_id={task_id}")

    # 加载 prompts/video_generator.md 模板用于执行追踪
    agent_prompt = load_prompt_template("video_generator")
    if agent_prompt:
        logger.info(f"已加载视频智能体提示词模板 ({len(agent_prompt)} 字符)")

    video_prompt = prompts.get("video_storyboard", "cinematic product demonstration video")
    ref_image_url = images[0].get("url") if images else None

    video_client = ProviderFactory.get_video_client("kling")
    vid_res = await video_client.generate_video(
        prompt=video_prompt,
        duration=5,
        aspect_ratio="16:9",
        image_url=ref_image_url,
    )

    video_url = vid_res.get("video_url", "")
    cost = vid_res.get("cost", 0.0)
    is_mock = vid_res.get("is_mock", 1)

    video_info = {
        "type": "video",
        "sub_type": "product_showcase",
        "url": video_url,
        "duration": vid_res.get("duration", 5),
        "aspect_ratio": vid_res.get("aspect_ratio", "16:9"),
        "is_mock": is_mock,
        "meta": {"model": vid_res.get("model", "kling-v1"), "fps": 30},
    }

    # 持久化写入 ac_asset 表
    if task_id and sku_id and video_url:
        try:
            async with AsyncSessionLocal() as session:
                asset_obj = Asset(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    sku_id=sku_id,
                    type="video",
                    sub_type="product_showcase",
                    url=video_url,
                    meta=video_info["meta"],
                    status="completed",
                    is_mock=is_mock,
                )
                session.add(asset_obj)
                await session.commit()
        except Exception as e:
            logger.warning(f"保存视频资产异常: {str(e)}")

    elapsed_ms = int((time.time() - start_time) * 1000)

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="video_generator",
        status="success",
        elapsed_ms=elapsed_ms,
        cost=cost,
        progress=85,
        input_data={"prompt": video_prompt, "ref_image": bool(ref_image_url)},
        output_data=video_info,
    )

    return {
        "current_step": "video_generator",
        "completed_steps": ["video_generator"],
        "generated_video": video_info,
    }
