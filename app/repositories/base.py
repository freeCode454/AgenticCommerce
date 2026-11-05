"""
Base Repository 泛型基类，强制附加 tenant_id 隔离
"""

from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T], session: AsyncSession):
        self.model_class = model_class
        self.session = session

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[T]:
        stmt = select(self.model_class).where(
            self.model_class.id == id,
            self.model_class.tenant_id == tenant_id,
            self.model_class.is_deleted == 0
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
