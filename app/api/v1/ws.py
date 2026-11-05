"""
WebSocket 实时事件分发器 (支持智能体工作流节点执行状态实时广播与任务监听)
"""

import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws")
router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    """管理全局 WebSocket 客户端连接与事件广播"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 客户端已连接，当前活跃连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket 客户端已断开，剩余连接数: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """异步广播事件至所有已连接前端客户端"""
        if not self.active_connections:
            return

        payload = json.dumps(message, ensure_ascii=False)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"WebSocket 消息发送失败: {str(e)}，标记清理连接")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

ws_manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 客户端心跳 ping/pong 处理
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket 连接异常: {str(e)}")
        ws_manager.disconnect(websocket)
