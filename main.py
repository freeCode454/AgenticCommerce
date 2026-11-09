"""
AgenticCommerce — 自主智能体电商平台
主应用入口文件 (FastAPI)
默认端口: 8002
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import asyncio
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from app.conf.config import settings
from app.clients.postgres import engine
from app.clients.redis import redis_client
from app.core.middlewares import RequestContextMiddleware
from app.core.deps import get_current_user_and_tenant
from fastapi import Depends, Request
from app.clients.provider_factory import EmbeddingAccessError, ProviderCallError
from app.core.provider_keys import ProviderConfigurationError
from fastapi.exceptions import RequestValidationError

# 预留生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.media_archive import archive_loop
    from app.services.task_worker import TaskWorker
    worker = TaskWorker()
    archive = None
    app.state.task_worker = worker
    try:
        if settings.TASK_WORKER_ENABLED:
            await worker.start()
            archive = asyncio.create_task(archive_loop(), name="media-archive")
        yield
    finally:
        if archive is not None:
            archive.cancel()
            await asyncio.gather(archive, return_exceptions=True)
        await worker.stop()
        await redis_client.aclose()
        await engine.dispose()

app = FastAPI(
    title="AgenticCommerce API",
    description="自主智能体电商平台 — 7-Agent 多智能体生成中台接口服务",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    lifespan=lifespan,
)

# 基础中间件栈配置（由内到外）
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1 import api_v1_router

# 注册 API v1 全量路由树
app.include_router(api_v1_router)


@app.exception_handler(ProviderCallError)
async def provider_unavailable(request: Request, exc: ProviderCallError):
    message = str(exc) if isinstance(exc, EmbeddingAccessError) else "模型服务不可用，请检查配置或稍后重试"
    return JSONResponse(status_code=502, content={"code": 502, "data": None, "message": message})


@app.exception_handler(ProviderConfigurationError)
async def provider_configuration_error(request: Request, exc: ProviderConfigurationError):
    return JSONResponse(status_code=503, content={"code":503, "data":None, "message":str(exc)})


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # Pydantic's default JSON includes the rejected input, which may be an API key.
    detail = [{"loc":error["loc"], "type":error["type"], "msg":error["msg"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"code":422, "data":None, "message":"请求参数无效，请核对填写内容。", "detail":detail})

@app.get("/health", tags=["System"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "AgenticCommerce",
        "version": "1.0.0"
    }

@app.get("/ready", tags=["System"])
async def readiness_check():
    from app.services.health_service import dependency_status
    dependencies = await dependency_status()
    ready = all(value == "ready" for value in dependencies.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "unavailable", "dependencies": dependencies},
    )


@app.get("/api/v1/system/status", tags=["System"])
async def system_status(user: dict = Depends(get_current_user_and_tenant)):
    from app.services.health_service import dependency_status
    return {"code": 200, "data": {
        "tenant_id": user["tenant_id"], "tenant_name": user["tenant_name"],
        "dependencies": await dependency_status(),
    }, "message": "获取成功"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=not settings.is_production)
