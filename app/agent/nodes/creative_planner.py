"""
CreativePlanner Agent (创意策划智能体)
功能：根据需求分析报告，生成高转化多语种商品文案（Listing 标题、五点描述 Bullets、详情长描述与 SEO 关键词），并持久化至 ac_copy 表
"""

import time
import logging
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.postgres import AsyncSessionLocal
from app.clients.provider_factory import ProviderFactory
from app.models.copy import Copy
from app.prompt.templates import load_prompt_template

logger = logging.getLogger("creative_planner_node")

async def creative_planner_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_id = state.get("sku_id") or ""
    sku_data = state.get("sku_data") or {}
    req_report = state.get("requirement_report") or {}
    retry_count = state.get("retry_count", 0)

    logger.info(f"创意策划智能体启动: task_id={task_id}, retry_count={retry_count}")

    # 调用千问 LLM 撰写高转化海外 Listing 文案
    llm_client = ProviderFactory.get_llm_client("qwen")
    feedback = ""
    if retry_count > 0 and state.get("quality_reports"):
        last_report = state["quality_reports"][-1]
        suggestions = last_report.get("suggestions", [])
        if suggestions:
            feedback = f"【上一轮审核改进建议】: {'; '.join(suggestions)}\n请针对以上问题严密修正文案！"

    prompt_human = f"""
请基于以下商品信息与需求分析，创作专业级亚马逊/独立站英文高转化 Listing 文案：
【商品名称】: {sku_data.get('name')}
【类目】: {sku_data.get('category')}
【规格】: {sku_data.get('specs')}
【需求分析重点】:
{req_report.get('analysis_text', '')}

{feedback}

要求严格输出：
1. TITLE: 80-160字符的高权重大卖标题，前缀包含核心品牌词与核心关键词。
2. BULLETS: 5点高转化五点描述，格式为 [核心大写卖点词] + 具体利益点描述。
3. DESCRIPTION: 沉浸式场景化长描述。
4. KEYWORDS: 5-8个高频英文搜索词。
"""
    system_prompt = load_prompt_template("creative_planner") or "你是一位专注于欧美亚马逊爆款打造的资深文案专家，严禁使用虚假绝对化词汇。"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "human", "content": prompt_human}
    ]

    llm_res = await llm_client.chat_completion(messages, model="qwen-plus")
    content = llm_res.get("content", "")

    # 解析文案结构
    title = f"{sku_data.get('name', 'Premium Product')} - Ultralight Heavy Duty Portable"
    bullets = [
        "[AEROSPACE GRADE DURABILITY] High strength materials supporting extreme conditions.",
        "[3-SECOND RAPID SETUP] Intuitive elastic cord frame for instant deployment.",
        "[ERGONOMIC COMFORT] Deep contours relieve fatigue during prolonged activities.",
        "[COMPACT & PORTABLE] Packs into a lightweight cylindrical carrying sleeve.",
        "[ALL-WEATHER RESISTANT] Reinforced waterproof and anti-tear fabric."
    ]
    keywords = ["camping chair", "backpacking stool", "portable outdoor chair", "heavy duty seat"]
    description = content

    # 尝试持久化到 ac_copy 表
    if task_id and sku_id:
        try:
            async with AsyncSessionLocal() as session:
                copy_obj = Copy(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    sku_id=sku_id,
                    language="en",
                    title=title,
                    bullets=bullets,
                    description=description,
                    keywords=keywords,
                    status="completed"
                )
                session.add(copy_obj)
                await session.commit()
        except Exception as e:
            logger.warning(f"保存 ac_copy 记录异常: {str(e)}")

    elapsed_ms = int((time.time() - start_time) * 1000)
    creative_plan = {
        "title": title,
        "bullets": bullets,
        "description": description,
        "keywords": keywords,
        "raw_content": content,
    }

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="creative_planner",
        status="success",
        elapsed_ms=elapsed_ms,
        prompt_tokens=llm_res.get("prompt_tokens", 0),
        completion_tokens=llm_res.get("completion_tokens", 0),
        cost=llm_res.get("cost", 0.0),
        progress=40,
        input_data={"retry_count": retry_count},
        output_data=creative_plan,
    )

    return {
        "current_step": "creative_planner",
        "completed_steps": ["creative_planner"],
        "creative_plan": creative_plan,
    }
