"""
商品 SKU 管理接口 (SKU Router)
薄路由层: 仅负责参数解析、权限检查与 HTTP 响应映射
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user_and_tenant
from app.services.sku_service import SkuService

router = APIRouter(prefix="/skus", tags=["商品SKU管理"])

class SkuCreateRequest(BaseModel):
    code: str
    name: str
    category: str
    specs: Dict[str, Any] = {}
    description: Optional[str] = None
    images: List[str] = []

class SkuUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    images: Optional[List[str]] = None


@router.get("")
async def list_skus(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """分页查询商品 SKU 列表"""
    svc = SkuService(db)
    items, total = await svc.list_skus(user_tenant["tenant_id"], page, page_size, q, category)
    return {"code": 200, "data": {"items": items, "total": total, "page": page, "page_size": page_size}, "message": "获取成功"}


@router.post("")
async def create_sku(
    req: SkuCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """新建商品 SKU"""
    svc = SkuService(db)
    try:
        result = await svc.create_sku(
            tenant_id=user_tenant["tenant_id"], user_id=user_tenant.get("user_id"),
            code=req.code, name=req.name, category=req.category,
            specs=req.specs, description=req.description, images=req.images,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 200, "data": result, "message": "商品创建成功"}


class SkuExtractSpecsRequest(BaseModel):
    description: str


@router.post("/extract-specs")
async def extract_sku_specs(
    req: SkuExtractSpecsRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """调用 SkuService 服务层从白话描述中提取结构化规格参数 (依赖 prompts/spec_extractor.md 提示词)"""
    if not req.description or not req.description.strip():
        raise HTTPException(status_code=400, detail="描述内容不能为空")

    svc = SkuService(db)
    result = await svc.extract_specs(req.description)
    return {
        "code": 200,
        "data": result.get("specs", {}),
        "is_mock": result.get("is_mock", 0),
        "model": result.get("model", ""),
        "message": "大模型结构化规格提取成功"
    }


@router.get("/{sku_id}")
async def get_sku(
    sku_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """获取单个商品 SKU 详情"""
    svc = SkuService(db)
    try:
        result = await svc.get_sku(user_tenant["tenant_id"], sku_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": result, "message": "获取成功"}


@router.put("/{sku_id}")
async def update_sku(
    sku_id: str,
    req: SkuUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """更新商品 SKU 信息"""
    svc = SkuService(db)
    try:
        result_id = await svc.update_sku(user_tenant["tenant_id"], sku_id, req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": {"id": result_id}, "message": "更新成功"}


@router.delete("/{sku_id}")
async def delete_sku(
    sku_id: str,
    db: AsyncSession = Depends(get_db),
    user_tenant: dict = Depends(get_current_user_and_tenant),
):
    """逻辑删除商品 SKU"""
    svc = SkuService(db)
    result_id = await svc.delete_sku(user_tenant["tenant_id"], sku_id)
    return {"code": 200, "data": {"id": result_id}, "message": "删除成功"}
