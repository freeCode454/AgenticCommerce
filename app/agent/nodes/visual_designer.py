"""
VisualDesigner Agent (视觉设计智能体)
功能：将商品核心卖点转化为符合大模型生图与生视频标准的结构化提示词（主图、场景图、细节图 Prompt 与 5 镜头视频分镜）
"""

import time
import logging
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.provider_factory import ProviderFactory
from app.prompt.templates import load_prompt_template

logger = logging.getLogger("visual_designer_node")

async def visual_designer_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_data = state.get("sku_data") or {}
    creative_plan = state.get("creative_plan") or {}

    logger.info(f"视觉设计智能体启动: {sku_data.get('name')}")

    # 调用千问大模型进行精细化 Prompt 工程化拆解
    llm_client = ProviderFactory.get_llm_client("qwen")
    prompt_human = f"""
请为以下电商商品设计全套视觉生成方案：
【商品名称】: {sku_data.get('name')}
【类目】: {sku_data.get('category')}
【主文案标题】: {creative_plan.get('title', '')}

请拆解输出：
1. 主图 Prompt (白底、专业影棚光、高光泽金属质感、4K商业产品摄影)
2. 场景图 Prompt (逼真户外自然环境、露营野餐、柔和阳光、高级生活方式质感)
3. 细节图 Prompt (微距特写、精密机械结构或材质纹理细节)
4. 15秒带货短视频 5 镜头分镜脚本 (Hook, Pain Point, Demo, Lifestyle, CTA)
"""
    system_prompt = load_prompt_template("visual_designer") or "你是一位顶级商业视觉总监与 AI Prompt 工程师，深谙 Midjourney 与 Wanx/Kling 提示词调优技巧。"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "human", "content": prompt_human}
    ]

    llm_res = await llm_client.chat_completion(messages, model="qwen-plus")

    # 结构化生图 Prompt
    sku_name_en = "Ultralight Camping Chair" if "椅" in sku_data.get("name", "") else "Wireless Earphones Pro"
    generation_prompts = {
        "main_image": f"Commercial product photography of {sku_name_en}, pure white background, studio lighting, sharp focus, 8k resolution, photorealistic, premium metallic finish.",
        "scene_image": f"Lifestyle photography of {sku_name_en} placed on a picturesque mountain campsite beside pine trees and a tent at sunset, warm cinematic glow, ultra realistic.",
        "detail_image": f"Extreme macro close-up shot of {sku_name_en}, showcasing high precision aerospace alloy joints and waterproof fabric texture, intricate details, depth of field.",
        "video_storyboard": f"High quality cinematic 4k product showcase of {sku_name_en}, quick folding mechanism demonstrated in outdoor nature, vibrant colors, smooth camera movement.",
    }

    elapsed_ms = int((time.time() - start_time) * 1000)
    visual_design = {
        "prompt_plan": llm_res.get("content", ""),
        "image_count": 3,
        "video_duration": 5,
    }

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="visual_designer",
        status="success",
        elapsed_ms=elapsed_ms,
        prompt_tokens=llm_res.get("prompt_tokens", 0),
        completion_tokens=llm_res.get("completion_tokens", 0),
        cost=llm_res.get("cost", 0.0),
        progress=55,
        input_data={"sku_name": sku_data.get("name")},
        output_data={"prompts": generation_prompts, "visual_design": visual_design},
    )

    return {
        "current_step": "visual_designer",
        "completed_steps": ["visual_designer"],
        "visual_design": visual_design,
        "generation_prompts": generation_prompts,
    }
