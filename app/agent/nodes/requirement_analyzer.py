"""
RequirementAnalyzer Agent (需求分析智能体)
功能：结合 RAG 向量知识库（品牌调性、合规词库），分析目标客群、提炼核心差异化卖点与 SEO 关键词
"""

import time
import logging
from sqlalchemy import select
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.postgres import AsyncSessionLocal
from app.clients.provider_factory import ProviderFactory
from app.models.knowledge import KnowledgeChunk
from app.prompt.templates import load_prompt_template

logger = logging.getLogger("requirement_analyzer_node")

async def requirement_analyzer_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_data = state.get("sku_data") or {}

    logger.info(f"需求分析智能体启动: sku={sku_data.get('name')}")

    # 1. 调用 Qwen LLM 生成查询向量
    llm_client = ProviderFactory.get_llm_client("qwen")
    search_query = f"{sku_data.get('category', '')} {sku_data.get('name', '')}"
    try:
        query_vector = await llm_client.get_embedding(search_query)
    except Exception as e:
        logger.warning(f"获取 Embedding 异常: {str(e)}")
        query_vector = [0.0] * 1024 # 兜底向量

    # 2. RAG 知识检索 (真实语义向量检索品牌规范与本土化调性)
    rag_context = ""
    try:
        async with AsyncSessionLocal() as session:
            from app.repositories.knowledge_repo import KnowledgeRepository
            repo = KnowledgeRepository(session)
            chunks = await repo.search_vectors(
                tenant_id=tenant_id, 
                query_vector=query_vector, 
                limit=3, 
                threshold=0.6
            )
            if chunks:
                rag_context = "\n".join([c.content for c in chunks])
    except Exception as e:
        logger.warning(f"RAG 检索知识分块异常: {str(e)}")
    prompt_human = f"""
请基于以下商品信息与品牌规范，进行出海电商需求深度分析：
【商品名称】: {sku_data.get('name', '户外商品')}
【所属类目】: {sku_data.get('category', '户外运动')}
【规格参数】: {sku_data.get('specs', {})}
【商品描述】: {sku_data.get('description', '')}

【品牌与合规规范 (RAG 检索)】:
{rag_context or '遵循海外主流电商平台合规标准，突出高品质与实用价值。'}

请输出以下结构化分析：
1. 目标受众画像（年龄、生活方式、核心痛点）
2. 3大核心差异化卖点（结合规格）
3. 核心 SEO 英文关键词（5-8个）
"""
    system_prompt = load_prompt_template("requirement_analyzer") or "你是一位拥有10年经验的跨境电商资深产品策划总监，擅长精准洞察海外消费者心理。"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt_human}
    ]

    llm_res = await llm_client.chat_completion(messages, model="qwen-plus")

    elapsed_ms = int((time.time() - start_time) * 1000)
    requirement_report = {
        "analysis_text": llm_res.get("content", ""),
        "rag_source_count": len(chunks) if 'chunks' in locals() else 0,
        "model_used": llm_res.get("model", "qwen-plus"),
        "cost": llm_res.get("cost", 0.0),
    }

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="requirement_analyzer",
        status="success",
        elapsed_ms=elapsed_ms,
        prompt_tokens=llm_res.get("prompt_tokens", 0),
        completion_tokens=llm_res.get("completion_tokens", 0),
        cost=llm_res.get("cost", 0.0),
        progress=25,
        input_data={"sku_name": sku_data.get("name"), "has_rag": bool(rag_context)},
        output_data=requirement_report,
    )

    return {
        "current_step": "requirement_analyzer",
        "completed_steps": ["requirement_analyzer"],
        "requirement_report": requirement_report,
    }
