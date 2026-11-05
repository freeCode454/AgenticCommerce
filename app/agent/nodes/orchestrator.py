"""
Orchestrator Agent (编排调度智能体)
功能：解析任务配置，拉取并校验商品 SKU 基础信息，初始化全局执行状态与路由流向
"""

import time
import logging
from sqlalchemy import select
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.postgres import AsyncSessionLocal
from app.models.sku import Sku
from app.prompt.templates import load_prompt_template

logger = logging.getLogger("orchestrator_node")

async def orchestrator_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_id = state.get("sku_id")
    sku_data = state.get("sku_data") or {}

    logger.info(f"编排调度智能体启动: task_id={task_id}, sku_id={sku_id}")

    # 如果状态中无 SKU 详情，从数据库查询并补充
    if not sku_data and sku_id:
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(Sku).where(Sku.id == sku_id))
                sku_obj = res.scalar_one_or_none()
                if sku_obj:
                    sku_data = {
                        "id": sku_obj.id,
                        "code": sku_obj.code,
                        "name": sku_obj.name,
                        "category": sku_obj.category,
                        "specs": sku_obj.specs,
                        "description": sku_obj.description,
                        "images": sku_obj.images,
                    }
        except Exception as e:
            logger.warning(f"读取 SKU 详情异常: {str(e)}")

    elapsed_ms = int((time.time() - start_time) * 1000)
    system_prompt = load_prompt_template("orchestrator")
    output_snapshot = {
        "status": "initialized",
        "system_prompt_loaded": bool(system_prompt),
        "sku_code": sku_data.get("code", "UNKNOWN"),
        "sku_name": sku_data.get("name", "Default Product"),
        "target_agents": [
            "requirement_analyzer",
            "creative_planner",
            "visual_designer",
            "image_generator",
            "video_generator",
            "quality_reviewer"
        ]
    }

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="orchestrator",
        status="success",
        elapsed_ms=elapsed_ms,
        progress=10,
        input_data={"sku_id": sku_id, "config": state.get("config", {})},
        output_data=output_snapshot,
    )

    return {
        "current_step": "orchestrator",
        "completed_steps": ["orchestrator"],
        "sku_data": sku_data,
        "retry_count": state.get("retry_count", 0),
        "max_retries": state.get("max_retries", 2),
    }
