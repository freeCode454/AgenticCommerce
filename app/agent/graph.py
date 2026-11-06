"""
LangGraph 7-Agent 工作流图构建与编译
实现 P-E-V (规划-执行-验证) 循环与质量审核条件路由
"""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.creative_planner import creative_planner_node
from app.agent.nodes.image_generator import image_generator_node
from app.agent.nodes.orchestrator import orchestrator_node
from app.agent.nodes.quality_reviewer import quality_reviewer_node
from app.agent.nodes.requirement_analyzer import requirement_analyzer_node
from app.agent.nodes.video_generator import video_generator_node
from app.agent.nodes.visual_designer import visual_designer_node
from app.agent.recorder import record_node_execution
from app.agent.state import AgentState
from app.core.task_execution import active_execution

logger = logging.getLogger("agent_graph")

def quality_review_router(state: AgentState) -> Literal["creative_planner", "__end__"]:
    """
    质量审核条件路由函数 (P-E-V 闭环):
    1. 若审核通过 (is_passed == True)，则直接流向 END 完成流程。
    2. 若未通过且重试次数小于上限 (retry_count < max_retries)，则携带反馈回退至 creative_planner 重新生成。
    3. 若超过最大重试次数，则终止流向 END 并标记人工介入。
    """
    is_passed = state.get("is_passed", False)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if is_passed:
        logger.info("质量审核通过，工作流顺利收敛至 END。")
        return END

    if state.get("should_retry", retry_count < max_retries):
        logger.warning(f"质量审核未通过，触发 P-E-V 回退循环！第 {retry_count} 次重试回退至 creative_planner...")
        return "creative_planner"

    logger.error(f"质量审核未通过且重试次数达到上限 ({max_retries})，流向 END 等待人工介入。")
    return END

def observed_node(name, function):
    async def execute(state: AgentState):
        if active_execution.get() is None:
            return await function(state)
        await record_node_execution(
            task_id=state["task_id"], tenant_id=state["tenant_id"], node_name=name, status="running",
        )
        try:
            return await function(state)
        except Exception as error:
            from app.core.generation import GenerationOutputError
            await record_node_execution(
                task_id=state["task_id"], tenant_id=state["tenant_id"], node_name=name,
                status="failed", output_data={"error_message": str(error) if isinstance(error, GenerationOutputError)
                                               else f"节点执行失败 ({type(error).__name__})，请检查配置后重试。"},
            )
            raise
    return execute


def build_workflow():
    """构建 7-Agent 有状态 DAG 工作流"""
    builder = StateGraph(AgentState)

    # 1. 注册 7 大核心智能体节点
    for name, node in (
        ("orchestrator", orchestrator_node), ("requirement_analyzer", requirement_analyzer_node),
        ("creative_planner", creative_planner_node), ("visual_designer", visual_designer_node),
        ("image_generator", image_generator_node), ("video_generator", video_generator_node),
        ("quality_reviewer", quality_reviewer_node),
    ):
        builder.add_node(name, observed_node(name, node))

    # 2. 编排线性拓扑流水线
    builder.add_edge(START, "orchestrator")
    builder.add_edge("orchestrator", "requirement_analyzer")
    builder.add_edge("requirement_analyzer", "creative_planner")
    builder.add_edge("creative_planner", "visual_designer")
    builder.add_edge("visual_designer", "image_generator")
    builder.add_edge("image_generator", "video_generator")
    builder.add_edge("video_generator", "quality_reviewer")

    # 3. 编排条件回退边 (P-E-V 循环)
    builder.add_conditional_edges(
        "quality_reviewer",
        quality_review_router,
        {
            "creative_planner": "creative_planner",
            END: END,
        }
    )

    return builder

# 编译为可直接执行的 CompiledGraph 实例
app_workflow = build_workflow().compile()
