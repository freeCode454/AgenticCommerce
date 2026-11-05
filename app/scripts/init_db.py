"""
数据库初始化脚本: 创建全部数据表并校验 pgvector 插件
"""

import asyncio
import logging
from sqlalchemy import text
from app.clients.postgres import engine
import app.models  # 必须导入全部模型以注册至 Base.metadata
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

async def init_db():
    logger.info("正在连接 PostgreSQL 16 (端口: 5434) 并初始化 pgvector 扩展...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        logger.info("pgvector 扩展已就绪，正在创建全部 14 张核心业务表...")
        await conn.run_sync(Base.metadata.create_all)
    
    table_names = list(Base.metadata.tables.keys())
    logger.info(f"全部数据表创建完毕！共注册 {len(table_names)} 张数据表:")
    for t in sorted(table_names):
        logger.info(f" - 表已就绪: {t}")

if __name__ == "__main__":
    asyncio.run(init_db())

