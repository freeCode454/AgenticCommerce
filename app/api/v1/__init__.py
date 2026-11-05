"""
API v1 Routers
"""
from fastapi import APIRouter
from .auth import router as auth_router
from .providers import router as providers_router
from .knowledge import router as knowledge_router
from .skus import router as skus_router
from .batches import router as batches_router
from .tasks import router as tasks_router
from .copies import router as copies_router
from .assets import router as assets_router
from .compliance import router as compliance_router
from .packages import router as packages_router
from .audit import router as audit_router
from .listings import router as listings_router
from .ws import router as ws_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(skus_router)
api_v1_router.include_router(batches_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(copies_router)
api_v1_router.include_router(assets_router)
api_v1_router.include_router(compliance_router)
api_v1_router.include_router(packages_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(listings_router)
api_v1_router.include_router(ws_router)
