"""
智能体节点执行快照记录器与 WebSocket 实时状态广播器
"""

import logging
from typing import Dict, Any, Optional
from app.clients.postgres import AsyncSessionLocal
from app.models.task_node_run import TaskNodeRun
from app.models.task import Task
from app.api.v1.ws import ws_manager
from sqlalchemy import update

logger = logging.getLogger("agent_recorder")

async def record_node_execution(
    task_id: Optional[str],
    tenant_id: str,
    node_name: str,
    status: str = "success",
    elapsed_ms: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost: float = 0.0,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    progress: int = 0,
):
    """持久化保存节点运行快照，并向前端工作台广播实时进度"""
    # 1. 广播 WebSocket 状态
    event = {
        "type": "node_update",
        "task_id": task_id,
        "node_name": node_name,
        "status": status,
        "progress": progress,
        "elapsed_ms": elapsed_ms,
        "cost": cost,
        "output_data": output_data or {},
    }
    await ws_manager.broadcast(event)

    # 2. 如果存在关联的任务 ID，则持久化写入 PostgreSQL
    if task_id:
        try:
            async with AsyncSessionLocal() as session:
                node_run = TaskNodeRun(
                    tenant_id=tenant_id or "tenant_default",
                    task_id=task_id,
                    node_name=node_name,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost=cost,
                    input_data=input_data or {},
                    output_data=output_data or {},
                    prompt_record={},
                )
                session.add(node_run)

                # 同步更新任务的当前节点与重试进度
                await session.execute(
                    update(Task)
                    .where(Task.id == task_id)
                    .values(current_node=node_name)
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"持久化记录节点 {node_name} 执行快照失败: {str(e)}")
