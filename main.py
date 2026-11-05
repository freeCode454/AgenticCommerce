"""
AgenticCommerce — 自主智能体电商平台
主应用入口文件 (FastAPI)
默认端口: 8002
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

# 预留生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化：连接池预热、向量插件检查等
    yield
    # 退出时释放资源

app = FastAPI(
    title="AgenticCommerce API",
    description="自主智能体电商平台 — 7-Agent 多智能体生成中台接口服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 基础中间件栈配置（由内到外）
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1 import api_v1_router

# 注册 API v1 全量路由树
app.include_router(api_v1_router)

@app.get("/health", tags=["System"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "AgenticCommerce",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
