"""
认证服务层 (AuthService)
核心业务: 用户登录验证、Token 签发、Token 刷新
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base import BaseService
from app.core.security import verify_password, create_access_token
from app.models.user import User

logger = logging.getLogger("auth_service")


class AuthService(BaseService):

    async def authenticate(self, email: str, password: str) -> dict:
        """
        验证邮箱密码并签发 JWT Token
        Returns: {"access_token": str, "user": dict}
        Raises: ValueError 如果认证失败
        """
        query = select(User).where(User.email == email, User.is_deleted == 0)
        result = await self.session.execute(query)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password):
            raise ValueError("邮箱或密码错误")

        if user.status != "active":
            raise ValueError("用户账号已被禁用")

        token_payload = {
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        }
        access_token = create_access_token(token_payload)

        logger.info(f"用户登录成功: {email}")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "tenant_id": user.tenant_id,
            },
        }

    @staticmethod
    def refresh_token(user_payload: dict) -> dict:
        """基于现有 payload 签发新 Token"""
        new_token = create_access_token(user_payload)
        return {"access_token": new_token, "token_type": "bearer"}
