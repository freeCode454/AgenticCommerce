"""
QualityReviewer Agent (质量审核智能体)
功能：针对文案合规性（违禁词/侵权词）、品牌调性契合度与视音频多媒体素材质量进行综合量化打分，生成合规报告并决定是否触发条件回退重试
"""

import time
import json
import logging
from app.agent.state import AgentState
from app.agent.recorder import record_node_execution
from app.clients.postgres import AsyncSessionLocal
from app.clients.provider_factory import ProviderFactory
from app.models.compliance import ComplianceReport
from app.models.task import Task
from app.prompt.templates import load_prompt_template
from sqlalchemy import update
from app.core.compliance import parse_review, rule_violations
from app.clients.provider_factory import ProviderCallError

logger = logging.getLogger("quality_reviewer_node")

async def quality_reviewer_node(state: AgentState) -> dict:
    start_time = time.time()
    task_id = state.get("task_id")
    tenant_id = state.get("tenant_id") or "tenant_default"
    sku_id = state.get("sku_id") or ""
    creative_plan = state.get("creative_plan") or {}
    images = state.get("generated_images") or []
    video = state.get("generated_video")
    retry_count = state.get("retry_count", 0)

    logger.info(f"质量审核智能体启动: task_id={task_id}, retry_count={retry_count}")

    # 调用大模型执行多维度质检评估
    llm_client = ProviderFactory.get_llm_client("qwen")
    prompt_human = f"""
请对以下跨境电商出海物料进行全方位质量与合规审核：
【标题】: {creative_plan.get('title')}
【五点描述】: {creative_plan.get('bullets')}
【长描述截选】: {creative_plan.get('description', '')[:300]}
【生成图片数】: {len(images)}
【生成视频】: {'已就绪' if video else '无'}

请严格按照 JSON 格式返回审核报告，格式如下：
{{
  "score": 95.0,
  "passed": 1,
  "dimensions": {{
    "brand_consistency": 96.0,
    "platform_compliance": 95.0,
    "readability": 98.0,
    "visual_quality": 92.0
  }},
  "violations": [],
  "suggestions": ["文案符合平台合规要求，无夸大宣传", "首图符合纯白底规范"]
}}
"""
    system_prompt = load_prompt_template("quality_reviewer") or "你是一位出海电商质检专家，具备严格的国际商标法、亚马逊合规政策与广告法审核能力。"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt_human}
    ]

    # 审核异常必须阻断，不能将不可用的模型结果当作通过。
    score, passed, dimensions = 0.0, 0, {}
    violations, suggestions = [], []
    llm_res = {}
    try:
        llm_res = await llm_client.chat_completion(messages, model="qwen-plus")
        parsed = parse_review(llm_res.get("content", ""))
        score, passed, dimensions = parsed.score, parsed.passed, parsed.dimensions
        violations, suggestions = list(parsed.violations), list(parsed.suggestions)
        if llm_res.get("is_mock"):
            violations.append("模拟审核结果不可自动批准交付")
    except (ValueError, TypeError, KeyError, IndexError, ProviderCallError):
        violations = ["审核服务不可用或返回格式无效"]
        suggestions = ["请重试审核或交由人工复核"]
        logger.warning("Review unavailable or invalid: task_id=%s", task_id)

    violations.extend(rule_violations(" ".join([
        str(creative_plan.get("title", "")), str(creative_plan.get("bullets", [])),
        str(creative_plan.get("description", "")),
    ])))
    media_type = (state.get("config") or {}).get("media_type", "both")
    if media_type in {"image", "both"} and (not images or any(not a.get("url") or a.get("is_mock") for a in images)):
        violations.append("缺少真实图片产物")
    if media_type in {"video", "both"} and (not video or not video.get("url") or video.get("is_mock")):
        violations.append("缺少真实视频产物")
    is_passed = passed == 1 and score >= 85.0 and not violations
    next_retry_count = retry_count + (0 if is_passed else 1)

    # 持久化写入 ac_compliance_report 表
    if task_id and sku_id:
        try:
            async with AsyncSessionLocal() as session:
                report_obj = ComplianceReport(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    sku_id=sku_id,
                    score=score,
                    dimensions=dimensions,
                    violations=violations,
                    passed=1 if is_passed else 0,
                    suggestions=suggestions,
                    status="passed" if is_passed else "rejected",
                )
                session.add(report_obj)

                # 更新任务主表状态
                new_status = "completed" if is_passed else ("retrying" if next_retry_count < state.get("max_retries", 2) else "failed")
                await session.execute(
                    update(Task)
                    .where(Task.id == task_id, Task.tenant_id == tenant_id, Task.is_deleted == 0)
                    .values(status=new_status, retry_count=next_retry_count)
                )
                await session.commit()
        except Exception as e:
            logger.error("Review persistence failed: task_id=%s, error=%s", task_id, type(e).__name__)
            raise

    elapsed_ms = int((time.time() - start_time) * 1000)
    current_report = {
        "score": score,
        "passed": 1 if is_passed else 0,
        "dimensions": dimensions,
        "violations": violations,
        "suggestions": suggestions,
        "round": retry_count + 1,
    }

    reports = list(state.get("quality_reports") or [])
    reports.append(current_report)

    await record_node_execution(
        task_id=task_id,
        tenant_id=tenant_id,
        node_name="quality_reviewer",
        status="success" if is_passed else "failed",
        elapsed_ms=elapsed_ms,
        prompt_tokens=llm_res.get("prompt_tokens", 0),
        completion_tokens=llm_res.get("completion_tokens", 0),
        cost=llm_res.get("cost", 0.0),
        progress=100 if is_passed else 90,
        input_data={"retry_count": retry_count},
        output_data=current_report,
    )

    return {
        "current_step": "quality_reviewer",
        "completed_steps": ["quality_reviewer"],
        "quality_reports": reports,
        "is_passed": is_passed,
        "violations": violations,
        "retry_count": next_retry_count,
    }
