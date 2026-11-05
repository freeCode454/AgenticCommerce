"""
初始化演示种子数据（初始租户、初始管理员、默认模型厂商配置、测试 SKU、品牌知识库）
"""

import asyncio
import logging
from sqlalchemy import select
from app.clients.postgres import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import (
    Tenant, User, Provider, Sku, KnowledgeBaseDoc, KnowledgeChunk
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_data")

async def seed_data():
    logger.info("正在检查并导入初始演示数据...")
    async with AsyncSessionLocal() as session:
        # 1. 检查或创建默认租户
        tenant_res = await session.execute(select(Tenant).where(Tenant.id == "tenant_default"))
        tenant = tenant_res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id="tenant_default",
                name="环球出海科技有限公司",
                status="active",
                plan="enterprise"
            )
            session.add(tenant)
            logger.info("创建默认租户: 环球出海科技有限公司 (ID: tenant_default)")

        # 2. 检查或创建初始管理员
        user_res = await session.execute(select(User).where(User.email == "admin@agentic.com"))
        user = user_res.scalar_one_or_none()
        if not user:
            user = User(
                id="usr_admin",
                tenant_id="tenant_default",
                name="系统管理员",
                email="admin@agentic.com",
                password=get_password_hash("admin123"),
                role="admin",
                status="active"
            )
            session.add(user)
            logger.info("创建初始管理员: admin@agentic.com / 初始密码: admin123")

        # 3. 初始模型厂商配置 (Qwen / Wanx / Kling)
        providers_data = [
            {
                "id": "prov_qwen",
                "type": "llm",
                "name": "通义千问 (Qwen-Max/Plus)",
                "api_key_enc": "",
                "config": {"model": "qwen-plus", "temperature": 0.7, "max_tokens": 2048},
                "is_default": 1
            },
            {
                "id": "prov_wanx",
                "type": "image",
                "name": "通义万相 (Wanx 2.1)",
                "api_key_enc": "",
                "config": {"model": "wanx2.1-t2i-turbo", "size": "1024*1024", "n": 1},
                "is_default": 1
            },
            {
                "id": "prov_kling",
                "type": "video",
                "name": "快手可灵 (Kling AI)",
                "api_key_enc": "",
                "config": {"model": "kling-v1", "duration": 5, "aspect_ratio": "16:9"},
                "is_default": 1
            }
        ]
        for p in providers_data:
            p_res = await session.execute(select(Provider).where(Provider.id == p["id"]))
            if not p_res.scalar_one_or_none():
                prov = Provider(
                    id=p["id"],
                    tenant_id="tenant_default",
                    type=p["type"],
                    name=p["name"],
                    api_key_enc=p["api_key_enc"],
                    config=p["config"],
                    is_default=p["is_default"]
                )
                session.add(prov)
                logger.info(f"初始化模型厂商: {p['name']} ({p['type']})")

        # 4. 初始测试 SKU
        skus_data = [
            {
                "id": "sku_camp01",
                "code": "SKU-2026-CAMP01",
                "name": "超轻航空铝合金户外便携露营椅",
                "category": "户外运动",
                "specs": {
                    "材质": "航空7075铝合金 + 600D加厚牛津布",
                    "重量": "1.1kg",
                    "承重": "150kg",
                    "收纳尺寸": "35*12*10cm",
                    "适用场景": "野营、徒步、钓鱼、自驾"
                },
                "description": "专为轻量化野营探险打造，3秒快速折叠收纳，符合人体工学靠背设计，兼具超高承重与便携透气体验。",
                "images": ["https://images.unsplash.com/photo-1510312305653-8ed496efae75?w=800"]
            },
            {
                "id": "sku_ear02",
                "code": "SKU-2026-EAR02",
                "name": "极光 Pro 主动混合降噪无线耳机",
                "category": "数码配件",
                "specs": {
                    "降噪深度": "-48dB",
                    "综合续航": "42小时",
                    "防水等级": "IPX5",
                    "蓝牙版本": "Bluetooth 5.4",
                    "振膜材质": "12mm复合生物振膜"
                },
                "description": "旗舰级主动降噪无线耳机，支持空间音频定位与自适应降噪，高清ENC三麦通话抗风噪，低延迟游戏模式。",
                "images": ["https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800"]
            }
        ]
        for s in skus_data:
            s_res = await session.execute(select(Sku).where(Sku.id == s["id"]))
            if not s_res.scalar_one_or_none():
                sku_obj = Sku(
                    id=s["id"],
                    tenant_id="tenant_default",
                    code=s["code"],
                    name=s["name"],
                    category=s["category"],
                    specs=s["specs"],
                    description=s["description"],
                    images=s["images"]
                )
                session.add(sku_obj)
                logger.info(f"初始化测试 SKU: {s['code']} - {s['name']}")

        # 5. 初始知识库文档与分块向量
        doc_res = await session.execute(select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.id == "doc_brand01"))
        if not doc_res.scalar_one_or_none():
            doc = KnowledgeBaseDoc(
                id="doc_brand01",
                tenant_id="tenant_default",
                category="brand",
                doc_type="brand_guideline",
                name="环球出海北美品牌调性与合规文案规范",
                file_path="docs/brand_guideline_na.md",
                vector_status="indexed"
            )
            session.add(doc)

            # 伪 1024 维归一化向量，供 pgvector 演示余弦相似度检索
            embedding_vector = [0.03125] * 1024
            chunk = KnowledgeChunk(
                id="chunk_brand01_1",
                tenant_id="tenant_default",
                doc_id="doc_brand01",
                doc_type="brand_guideline",
                chunk_index=1,
                content=(
                    "品牌核心主张：科技引领，品质无界。目标客群：25-45岁追求高品质户外生活与精致科技体验的全球消费者。"
                    "视觉风格统一为极简、硬核工业感与自然高级光影。文案风格避免使用绝对化词汇（如‘世界第一’、‘绝对安全’），"
                    "多用数据论证与真实使用场景打动用户，突出环保耐用性与科技人文关怀。"
                ),
                embedding=embedding_vector,
                metadata_json={"source": "brand_guideline_na.md", "category": "brand"}
            )
            session.add(chunk)
            logger.info("初始化品牌知识库文档与 pgvector 向量分块数据")

        await session.commit()
    logger.info("全部初始演示种子数据填充完毕！")

if __name__ == "__main__":
    asyncio.run(seed_data())
