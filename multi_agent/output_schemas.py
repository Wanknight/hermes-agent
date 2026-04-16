"""
Output Schemas - Pydantic 输出模型定义

定义各 Agent 的输出 Schema，用于：
1. 验证 LLM 输出格式
2. 提供类型提示和文档
3. 支持自动修复和容错
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型"""
    CHAT = "chat"
    DECREE = "decree"


# ============================================================================
# 太子分类输出
# ============================================================================

class ClassificationOutput(BaseModel):
    """太子分类输出
    
    用于分类用户消息是闲聊还是旨意（任务）
    """
    type: MessageType = Field(
        description="消息类型: chat(闲聊) 或 decree(旨意)"
    )
    
    # 闲聊时使用
    response: Optional[str] = Field(
        default=None,
        description="闲聊回复内容"
    )
    
    # 旨意时使用
    title: Optional[str] = Field(
        default=None,
        description="旨意标题"
    )
    description: Optional[str] = Field(
        default=None,
        description="旨意详细描述"
    )
    category: Optional[str] = Field(
        default=None,
        description="任务分类"
    )
    urgency: Optional[Literal["低", "中", "高", "紧急"]] = Field(
        default=None,
        description="紧急程度"
    )
    complexity: Optional[Literal["简单", "中等", "复杂"]] = Field(
        default=None,
        description="复杂程度"
    )
    suggested_agents: Optional[List[str]] = Field(
        default=None,
        description="建议的执行Agent列表"
    )
    
    model_config = {
        "extra": "ignore",  # 忽略额外字段
    }


# ============================================================================
# 中书省规划输出
# ============================================================================

class PlanStep(BaseModel):
    """规划步骤"""
    step: int = Field(
        description="步骤编号",
        ge=1
    )
    action: str = Field(
        description="步骤动作描述"
    )
    agent: str = Field(
        description="负责的Agent"
    )
    dependencies: List[int] = Field(
        default_factory=list,
        description="依赖的步骤编号"
    )
    estimated_time: Optional[str] = Field(
        default=None,
        description="预估时间"
    )


class PlanPhase(BaseModel):
    """规划阶段"""
    phase: int = Field(description="阶段编号")
    name: str = Field(description="阶段名称")
    steps: List[PlanStep] = Field(description="阶段步骤")


class PlanOutput(BaseModel):
    """中书省规划输出
    
    用于规划任务执行方案
    """
    analysis: str = Field(
        description="任务分析"
    )
    phases: List[PlanPhase] = Field(
        default_factory=list,
        description="执行阶段列表"
    )
    steps: List[PlanStep] = Field(
        default_factory=list,
        description="执行步骤列表（备用）"
    )
    resources: List[str] = Field(
        default_factory=list,
        description="所需资源"
    )
    risks: List[str] = Field(
        default_factory=list,
        description="风险提示"
    )
    estimated_total_time: Optional[str] = Field(
        default=None,
        description="预估总时间"
    )
    
    model_config = {
        "extra": "ignore",
    }


# ============================================================================
# 门下省审议输出
# ============================================================================

class ReviewScore(BaseModel):
    """审议评分"""
    feasibility: int = Field(
        default=7,
        description="可行性评分 (0-10)",
        ge=0,
        le=10
    )
    completeness: int = Field(
        default=7,
        description="完整性评分 (0-10)",
        ge=0,
        le=10
    )
    risk_management: int = Field(
        default=7,
        description="风险管理评分 (0-10)",
        ge=0,
        le=10
    )
    resource_allocation: int = Field(
        default=7,
        description="资源分配评分 (0-10)",
        ge=0,
        le=10
    )


class ReviewOutput(BaseModel):
    """门下省审议输出
    
    用于审议任务规划方案
    """
    decision: Literal["approved", "rejected"] = Field(
        description="审议决定: approved(通过) 或 rejected(驳回)"
    )
    scores: Optional[ReviewScore] = Field(
        default=None,
        description="各项评分"
    )
    total_score: Optional[int] = Field(
        default=None,
        description="总分"
    )
    comments: Optional[str] = Field(
        default=None,
        description="审议意见"
    )
    issues: Optional[List[str]] = Field(
        default=None,
        description="发现的问题"
    )
    suggestions: Optional[List[str]] = Field(
        default=None,
        description="改进建议"
    )
    reason: Optional[str] = Field(
        default=None,
        description="决定原因"
    )
    
    model_config = {
        "extra": "ignore",
    }


# ============================================================================
# 尚书省派发输出
# ============================================================================

class DispatchItem(BaseModel):
    """派发项"""
    agent: str = Field(
        description="执行Agent"
    )
    task: str = Field(
        description="任务内容"
    )
    priority: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="优先级"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="依赖的其他派发项"
    )


class DispatchOutput(BaseModel):
    """尚书省派发输出
    
    用于派发任务到六部执行
    """
    dispatches: List[DispatchItem] = Field(
        default_factory=list,
        description="派发列表"
    )
    execution_order: List[str] = Field(
        default_factory=list,
        description="执行顺序"
    )
    parallel_groups: List[List[str]] = Field(
        default_factory=list,
        description="可并行执行的组"
    )
    
    model_config = {
        "extra": "ignore",
    }


# ============================================================================
# 六部执行输出
# ============================================================================

class ExecutionOutput(BaseModel):
    """六部执行输出
    
    通用执行结果格式
    """
    success: bool = Field(
        default=True,
        description="执行是否成功"
    )
    result: str = Field(
        default="",
        description="执行结果描述"
    )
    output: Optional[str] = Field(
        default=None,
        description="详细输出内容"
    )
    files_created: List[str] = Field(
        default_factory=list,
        description="创建的文件列表"
    )
    files_modified: List[str] = Field(
        default_factory=list,
        description="修改的文件列表"
    )
    commands_run: List[str] = Field(
        default_factory=list,
        description="执行的命令列表"
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="建议的后续步骤"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="遇到的错误"
    )
    
    model_config = {
        "extra": "ignore",
    }


# ============================================================================
# Schema 映射
# ============================================================================

# Agent ID 到输出 Schema 的映射
AGENT_OUTPUT_SCHEMAS: Dict[str, type[BaseModel]] = {
    "taizi": ClassificationOutput,
    "zhongshu": PlanOutput,
    "menxia": ReviewOutput,
    "shangshu": DispatchOutput,
    # 六部使用通用执行输出
    "hubu": ExecutionOutput,
    "libu": ExecutionOutput,
    "bingbu": ExecutionOutput,
    "xingbu": ExecutionOutput,
    "gongbu": ExecutionOutput,
    "libu_hr": ExecutionOutput,
}


def get_output_schema(agent_id: str) -> Optional[type[BaseModel]]:
    """获取 Agent 的输出 Schema
    
    Args:
        agent_id: Agent ID
        
    Returns:
        Pydantic 模型类，如果没有定义则返回 None
    """
    return AGENT_OUTPUT_SCHEMAS.get(agent_id)
