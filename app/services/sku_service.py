"""
商品 SKU 服务层 (SkuService)
核心业务: SKU 的增删改查、编码唯一性校验
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update
from app.services.base import BaseService
from app.models.sku import Sku

logger = logging.getLogger("sku_service")


class SkuService(BaseService):

    async def list_skus(
        self, tenant_id: str, page: int = 1, page_size: int = 10,
        q: Optional[str] = None, category: Optional[str] = None,
    ) -> tuple:
        """分页查询 SKU 列表, 返回 (items_dicts, total)"""
        query = select(Sku).where(Sku.tenant_id == tenant_id, Sku.is_deleted == 0)
        if q:
            query = query.where((Sku.code.ilike(f"%{q}%")) | (Sku.name.ilike(f"%{q}%")))
        if category:
            query = query.where(Sku.category == category)
        query = query.order_by(Sku.create_time.desc())

        items, total = await self.paginate(query, page, page_size)
        return [self._to_dict(s) for s in items], total

    async def create_sku(
        self, tenant_id: str, user_id: str,
        code: str, name: str, category: str,
        specs: Dict[str, Any] = None, description: str = None, images: List[str] = None,
    ) -> dict:
        """创建 SKU, 如果 code 已存在则抛异常"""
        check = await self.session.execute(
            select(Sku).where(Sku.tenant_id == tenant_id, Sku.code == code, Sku.is_deleted == 0)
        )
        if check.scalar_one_or_none():
            raise ValueError(f"商品编码 {code} 已存在")

        # 智能兜底：若用户未手动配置/未点击提取，但填写了商品描述，入库前自动触发大模型提取
        final_specs = specs or {}
        if not final_specs and description and description.strip():
            try:
                extracted = await self.extract_specs(description)
                if extracted.get("specs"):
                    final_specs = extracted.get("specs")
                    logger.info(f"保存 SKU {code} 时自动触发大模型抽取补全 specs: {final_specs}")
            except Exception as e:
                logger.warning(f"自动提取 specs 兜底失败: {str(e)}")

        sku = Sku(
            tenant_id=tenant_id, code=code, name=name, category=category,
            specs=final_specs, description=description or "", images=images or [],
            created_by=user_id,
        )
        self.session.add(sku)
        await self.session.commit()
        await self.session.refresh(sku)
        logger.info(f"新建 SKU: {code} / {name}")
        return {"id": sku.id, "code": sku.code, "name": sku.name}

    async def get_sku(self, tenant_id: str, sku_id: str) -> dict:
        """查询单个 SKU 详情"""
        sku = await self._get_or_404(tenant_id, sku_id)
        return self._to_dict(sku)

    async def update_sku(self, tenant_id: str, sku_id: str, update_data: dict) -> str:
        """更新 SKU 非空字段"""
        await self._get_or_404(tenant_id, sku_id)
        clean = {k: v for k, v in update_data.items() if v is not None}
        if clean:
            await self.session.execute(update(Sku).where(Sku.id == sku_id).values(**clean))
            await self.session.commit()
        return sku_id

    async def delete_sku(self, tenant_id: str, sku_id: str) -> str:
        """逻辑删除"""
        await self.session.execute(
            update(Sku).where(Sku.tenant_id == tenant_id, Sku.id == sku_id).values(is_deleted=1)
        )
        await self.session.commit()
        return sku_id

    async def extract_specs(self, description: str) -> dict:
        """从白话长描述中提取结构化规格参数 (基于独立 Prompt 模版与 Qwen LLM 服务)"""
        import json
        import re
        from app.prompt.templates import render_prompt_template
        from app.clients.provider_factory import ProviderFactory

        # 1. 从 prompts/spec_extractor.md 独立加载与渲染提示词
        rendered_prompt = render_prompt_template("spec_extractor", description=description)

        # 2. 调用模型服务层
        llm = ProviderFactory.get_llm_client()
        messages = [{"role": "user", "content": rendered_prompt}]

        res = await llm.chat_completion(messages=messages, temperature=0.1)
        content = res.get("content", "").strip()

        # 3. 提取与清洗 JSON 对象
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

        try:
            specs_dict = json.loads(content)
            if isinstance(specs_dict, dict):
                return {
                    "specs": specs_dict,
                    "is_mock": res.get("is_mock", 0),
                    "model": res.get("model", ""),
                }
        except Exception as e:
            logger.warning(f"大模型提取规格参数 JSON 解析失败: {str(e)}, content: {content}")

        return {"specs": {}, "is_mock": res.get("is_mock", 0), "model": res.get("model", "")}

    # ─── private helpers ───

    async def _get_or_404(self, tenant_id: str, sku_id: str) -> Sku:
        res = await self.session.execute(
            select(Sku).where(Sku.tenant_id == tenant_id, Sku.id == sku_id, Sku.is_deleted == 0)
        )
        sku = res.scalar_one_or_none()
        if not sku:
            raise ValueError("商品 SKU 不存在")
        return sku

    @staticmethod
    def _to_dict(s: Sku) -> dict:
        return {
            "id": s.id, "code": s.code, "name": s.name, "category": s.category,
            "specs": s.specs, "description": s.description, "images": s.images,
            "create_time": s.create_time.isoformat() if s.create_time else None,
        }
