"""
用户与认证接口 (Auth Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证管理"])

class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户邮箱密码登录，签发 JWT Access Token"""
    svc = AuthService(db)
    try:
        result = await svc.authenticate(req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"code": 200, "data": result, "message": "登录成功"}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user_and_tenant)):
    """获取当前登录用户信息与租户上下文"""
    return {"code": 200, "data": user, "message": "获取成功"}


@router.post("/refresh")
async def refresh_token(user: dict = Depends(get_current_user_and_tenant)):
    """刷新访问令牌"""
    result = AuthService.refresh_token(user)
    return {"code": 200, "data": result, "message": "令牌刷新成功"}
