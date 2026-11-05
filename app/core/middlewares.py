"""
核心自定义中间件 (RequestContextMiddleware & GlobalGuardMiddleware)
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.time()
        
        response: Response = await call_next(request)
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{(time.time() - start_time) * 1000:.2f}ms"
        return response

class GlobalGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 预留限流与安全防护
        return await call_next(request)
