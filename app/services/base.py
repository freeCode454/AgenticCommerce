"""
Service 层基类
提供统一的数据库会话注入和通用 CRUD 操作
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseService:
    """所有 Service 的基类，持有当前请求的 DB Session"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def paginate(
        self, query, page: int = 1, page_size: int = 10
    ) -> tuple:
        """通用分页: 返回 (items_list, total_count)"""
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        items = result.scalars().all()
        return items, total
