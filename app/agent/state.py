"""
AgentState: LangGraph 状态图共享状态定义
"""

from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated
import operator

class AgentState(TypedDict, total=False):
    # 基础元数据
    task_id: str
    tenant_id: str
    sku_id: str
    batch_id: Optional[str]
    config: Dict[str, Any]
    
    # 状态控制
    current_step: str
    completed_steps: Annotated[List[str], operator.add]
    retry_count: int
    max_retries: int
    
    # 业务产出物
    sku_data: Dict[str, Any]
    requirement_report: Dict[str, Any]
    creative_plan: Dict[str, Any]
    visual_design: Dict[str, Any]
    generation_prompts: Dict[str, Any]
    generated_images: List[Dict[str, Any]]
    generated_video: Optional[Dict[str, Any]]
    
    # 审核与路由
    quality_reports: List[Dict[str, Any]]
    is_passed: bool
    violations: List[Dict[str, Any]]
    error: Optional[str]
