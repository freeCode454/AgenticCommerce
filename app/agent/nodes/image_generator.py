"""
ImageGenerator Agent (图片生成智能体)
功能：调用通义万相 Wanx 2.1 异步生图 API 生成多视角高精商业素材（白底主图、生活场景图、微距特写图），并保存至 ac_asset 表
"""

import time
import logging
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.postgres import AsyncSessionLocal
from app.clients.provider_factory import ProviderFactory
from app.models.asset import Asset
from app.prompt.templates import load_prompt_template

logger = logging.getLogger("image_generator_node")

async def image_generator_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_id = state.get("sku_id") or ""
    prompts = state.get("generation_prompts") or {}

    logger.info(f"图片生成智能体启动: task_id={task_id}")

    # 加载 prompts/image_generator.md 模板用于执行追踪
    agent_prompt = load_prompt_template("image_generator")
    if agent_prompt:
        logger.info(f"已加载图片智能体提示词模板 ({len(agent_prompt)} 字符)")

    image_client = ProviderFactory.get_image_client("wanx")
    generated_assets = []
    total_cost = 0.0

    # 1. 批量生成 3 种典型视角素材
    sub_types = [
        ("main", prompts.get("main_image", "product on white background")),
        ("scene", prompts.get("scene_image", "product in outdoor campsite")),
        ("detail", prompts.get("detail_image", "product close up texture")),
    ]

    for sub_type, prompt_str in sub_types:
        # 增加延迟避免触发阿里云 DashScope API QPS 限制导致回退到 Mock
        import asyncio
        await asyncio.sleep(1.5)
        
        img_res = await image_client.generate_images(prompt=prompt_str, n=1, size="1024*1024")
        urls = img_res.get("urls", [])
        total_cost += img_res.get("cost", 0.0)
        is_mock = img_res.get("is_mock", 1)

        for u in urls:
            asset_info = {
                "type": "image",
                "sub_type": sub_type,
                "url": u,
                "prompt": prompt_str,
                "is_mock": is_mock,
                "meta": {"size": "1024*1024", "model": img_res.get("model", "wanx2.1")},
            }
            generated_assets.append(asset_info)

            # 持久化写入 ac_asset 表
            if task_id and sku_id:
                try:
                    async with AsyncSessionLocal() as session:
                        asset_obj = Asset(
                            tenant_id=tenant_id,
                            task_id=task_id,
                            sku_id=sku_id,
                            type="image",
                            sub_type=sub_type,
                            url=u,
                            meta=asset_info["meta"],
                            status="completed",
                            is_mock=is_mock,
                        )
                        session.add(asset_obj)
                        await session.commit()
                except Exception as e:
                    logger.warning(f"保存图片资产异常: {str(e)}")

    elapsed_ms = int((time.time() - start_time) * 1000)

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="image_generator",
        status="success",
        elapsed_ms=elapsed_ms,
        cost=total_cost,
        progress=70,
        input_data={"sub_types": [s[0] for s in sub_types]},
        output_data={"image_count": len(generated_assets), "assets": generated_assets},
    )

    return {
        "current_step": "image_generator",
        "completed_steps": ["image_generator"],
        "generated_images": generated_assets,
    }
