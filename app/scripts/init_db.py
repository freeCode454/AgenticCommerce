"""
数据库初始化脚本: 创建全部数据表并校验 pgvector 插件
"""

from pathlib import Path
from alembic import command
from alembic.config import Config


def init_db() -> None:
    command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head")

if __name__ == "__main__":
    init_db()

