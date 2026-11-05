"""
FastAPI 依赖注入（租户上下文、当前用户、数据库会话）
"""

from typing import AsyncGenerator, Optional, Dict, Any
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token
from app.clients.postgres import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库异步会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_user_and_tenant(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """从 JWT Authorization 头解析租户 ID 与当前用户信息；若无 Token 则使用默认初始租户与管理员"""
    if not authorization or not authorization.startswith("Bearer "):
        return {
            "user_id": "usr_admin",
            "tenant_id": "tenant_default",
            "name": "系统管理员",
            "email": "admin@agentic.com",
            "role": "admin"
        }
    
    token = authorization.split(" ")[1]
    try:
        payload = decode_token(token)
        return payload
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的访问令牌 (Invalid or expired token)"
        )
