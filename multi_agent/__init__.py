"""
Multi-Agent Module - 三省六部多Agent协作系统

This module implements a hierarchical multi-agent collaboration system
inspired by the ancient Chinese government structure "三省六部制".

Architecture:
- 太子 (Taizi): Message classification and routing
- 中书省 (Zhongshu): Planning and decision-making
- 门下省 (Menxia): Review and approval
- 尚书省 (Shangshu): Execution and dispatch
- 六部 (Six Ministries): Domain-specific execution
  - 户部 (Hubu): Data and reports
  - 兵部 (Bingbu): Infrastructure
  - 礼部 (Libu): Documentation and UI
  - 刑部 (Xingbu): Testing and compliance
  - 工部 (Gongbu): Development and code
  - 吏部 (Libu_hr): Configuration management
  - 早朝官 (Zaochao): Scheduled tasks

Usage:
    from multi_agent import MultiAgentOrchestrator
    
    orchestrator = MultiAgentOrchestrator(config)
    if orchestrator.is_enabled():
        result = orchestrator.process_message(user_message, context)
        
    # 查看统计信息
    stats = orchestrator.get_statistics()
"""

from .agent_loader import AgentLoader, AgentRole, get_agent_prompt, list_available_agents
from .orchestrator import MultiAgentOrchestrator, TaskContext, TaskStatus, MessageType, ProgressEvent
from .agent_pool import AgentPool
from .state_manager import MultiAgentStateManager, TaskRecord, AgentRunRecord, EventRecord

__all__ = [
    # Core
    "AgentLoader",
    "AgentRole",
    "AgentPool",
    "MultiAgentOrchestrator",
    "TaskContext",
    "TaskStatus",
    "MessageType",
    "ProgressEvent",
    # State Management
    "MultiAgentStateManager",
    "TaskRecord",
    "AgentRunRecord",
    "EventRecord",
    # Helpers
    "get_agent_prompt",
    "list_available_agents",
]

__version__ = "0.2.1"
