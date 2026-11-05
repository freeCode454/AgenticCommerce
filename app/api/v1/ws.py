"""
WebSocket 实时事件分发器 (支持智能体工作流节点执行状态实时广播与任务监听)
"""

import asyncio
import time
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.conf.config import settings
from app.core.deps import authenticate_token, get_db
from app.models.task import Task

logger = logging.getLogger("ws")
router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    """管理全局 WebSocket 客户端连接与事件广播"""

    def __init__(self):
        self.connections: dict[WebSocket, tuple[str, str, float]] = {}

    def connect(self, websocket: WebSocket, tenant_id: str, task_id: str, expires: float) -> None:
        self.connections[websocket] = (tenant_id, task_id, expires)

    def disconnect(self, websocket: WebSocket):
        self.connections.pop(websocket, None)

    async def broadcast(self, message: Dict[str, Any], *, tenant_id: str):
        """Only deliver to authorized subscriptions for this tenant and task."""
        for connection, (owner, task_id, expires) in list(self.connections.items()):
            if owner != tenant_id or task_id != message.get("task_id"):
                continue
            try:
                if expires <= time.time():
                    await connection.close(code=4401)
                    self.disconnect(connection)
                    continue
                await asyncio.wait_for(connection.send_json(message), timeout=5)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()

@router.websocket("/ws/tasks/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str, db: AsyncSession = Depends(get_db)):
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.CORS_ORIGINS:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    try:
        # Authenticate in the first frame, keeping credentials out of URL/access logs.
        frame = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        if not isinstance(frame, dict) or frame.get("type") != "authenticate" or not isinstance(frame.get("token"), str):
            await websocket.close(code=4401)
            return
        user = await authenticate_token(frame["token"], db)
        task = (await db.execute(select(Task).where(
            Task.id == task_id, Task.tenant_id == user["tenant_id"], Task.is_deleted == 0,
        ))).scalar_one_or_none()
        if task is None:
            await websocket.close(code=4404)
            return
        await db.rollback()
        ws_manager.connect(websocket, user["tenant_id"], task_id, user["exp"])
        await websocket.send_json({"type": "authenticated", "task_id": task_id})
        while True:
            remaining = user["exp"] - time.time()
            if remaining <= 0:
                await websocket.close(code=4401)
                return
            data = await asyncio.wait_for(websocket.receive_text(), timeout=min(60, remaining))
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except (HTTPException, ValueError, asyncio.TimeoutError):
        await websocket.close(code=4401)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("WebSocket subscription failed: task_id=%s", task_id)
        await websocket.close(code=1011)
    finally:
        ws_manager.disconnect(websocket)
