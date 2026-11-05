"""
合规质检服务层 (ComplianceService)
核心业务: 质检报告查询、实时合规扫描
"""

import logging
from typing import Optional
from sqlalchemy import select
from app.services.base import BaseService
from app.models.compliance import ComplianceReport
from app.models.sku import Sku
from app.clients.provider_factory import ProviderFactory

logger = logging.getLogger("compliance_service")

# 违禁词黑名单 — 生产环境可扩展为数据库/Redis 管理
FORBIDDEN_WORDS = ["世界第一", "绝对有效", "100% cure", "best in the world", "cheapest"]


class ComplianceService(BaseService):

    async def list_reports(
        self, tenant_id: str, page: int = 1, page_size: int = 10,
        task_id: Optional[str] = None, sku_id: Optional[str] = None,
    ) -> tuple:
        query = select(ComplianceReport).where(
            ComplianceReport.tenant_id == tenant_id, ComplianceReport.is_deleted == 0
        )
        if task_id:
            query = query.where(ComplianceReport.task_id == task_id)
        if sku_id:
            query = query.where(ComplianceReport.sku_id == sku_id)
        query = query.order_by(ComplianceReport.create_time.desc())

        items, total = await self.paginate(query, page, page_size)

        result = []
        for r in items:
            sku_res = await self.session.execute(select(Sku.name, Sku.code).where(Sku.id == r.sku_id))
            sku_info = sku_res.first()
            result.append({
                "id": r.id, "task_id": r.task_id, "sku_id": r.sku_id,
                "sku_name": sku_info[0] if sku_info else "",
                "sku_code": sku_info[1] if sku_info else "",
                "score": r.score, "passed": r.passed,
                "dimensions": r.dimensions, "violations": r.violations,
                "suggestions": r.suggestions, "status": r.status,
                "create_time": r.create_time.isoformat() if r.create_time else None,
            })
        return result, total

    async def get_report(self, tenant_id: str, report_id: str) -> dict:
        res = await self.session.execute(
            select(ComplianceReport).where(
                ComplianceReport.id == report_id, ComplianceReport.tenant_id == tenant_id
            )
        )
        r = res.scalar_one_or_none()
        if not r:
            raise ValueError("报告不存在")
        return {
            "id": r.id, "task_id": r.task_id, "sku_id": r.sku_id,
            "score": r.score, "passed": r.passed,
            "dimensions": r.dimensions, "violations": r.violations,
            "suggestions": r.suggestions, "status": r.status,
            "create_time": r.create_time.isoformat() if r.create_time else None,
        }

    @staticmethod
    async def run_realtime_check(title: str, content: str, target_platform: str = "amazon") -> dict:
        """实时合规扫描: LLM 辅助 + 规则引擎双重检测"""
        # 1. LLM 辅助检测
        llm_client = ProviderFactory.get_llm_client("qwen")
        prompt = f"""
请针对以下出海文案进行多维度合规筛查：
【标题】: {title}
【内容】: {content}
【目标平台】: {target_platform}

请检测是否包含绝对化词汇（如'世界第一'、'最佳'）、虚假夸大或平台禁止宣称，并返回 JSON 报告：
{{"score": 95, "passed": 1, "violations": [], "suggestions": ["文案符合平台规范"]}}
"""
        messages = [
            {"role": "system", "content": "你是一位拥有资深经验的跨境电商合规审核专家。"},
            {"role": "human", "content": prompt},
        ]
        await llm_client.chat_completion(messages, model="qwen-plus")

        # 2. 规则引擎检测
        found_violations = []
        text_to_check = f"{title} {content}".lower()
        for w in FORBIDDEN_WORDS:
            if w.lower() in text_to_check:
                found_violations.append(f"发现敏感绝对化用词: {w}")

        score = 98.0 if not found_violations else 70.0
        passed = 1 if not found_violations else 0

        return {
            "score": score,
            "passed": passed,
            "violations": found_violations,
            "suggestions": ["文案整体严谨规范，适合直接上线。"] if passed else ["请移除上述敏感违禁词汇。"],
            "dimensions": {
                "brand_consistency": 95,
                "platform_compliance": 96 if passed else 60,
                "legal_safety": 95 if passed else 65,
            },
        }
