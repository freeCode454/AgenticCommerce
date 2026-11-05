"""
FastAPI 依赖注入（租户上下文、当前用户、数据库会话）
"""

from typing import AsyncGenerator, Optional, Dict, Any
import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token
from app.clients.postgres import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User
from app.models.tenant import Tenant

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库异步会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请登录或重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authenticate_token(token: str, db: AsyncSession) -> Dict[str, Any]:
    """验证签名及当前用户/租户状态，以数据库中的角色为准。"""
    try:
        payload = decode_token(token)
    except (ValueError, TypeError, OverflowError, jwt.InvalidTokenError):
        raise unauthorized() from None
    user = (await db.execute(
        select(User).where(
            User.id == payload["user_id"], User.tenant_id == payload["tenant_id"],
            User.is_deleted == 0, User.status == "active",
        )
    )).scalar_one_or_none()
    tenant = (await db.execute(
        select(Tenant).where(
            Tenant.id == payload["tenant_id"], Tenant.is_deleted == 0,
            Tenant.status == "active",
        )
    )).scalar_one_or_none()
    if user is None or tenant is None:
        raise unauthorized()
    return {
        "user_id": user.id, "tenant_id": user.tenant_id, "name": user.name,
        "email": user.email, "role": user.role, "exp": payload["exp"], "type": "access",
        "tenant_name": tenant.name,
    }


async def get_current_user_and_tenant(
    authorization: Optional[str] = Header(None), db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    if not authorization:
        raise unauthorized()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized()
    return await authenticate_token(token.strip(), db)


async def require_admin(user: dict = Depends(get_current_user_and_tenant)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="此操作需要管理员权限")
    return user
