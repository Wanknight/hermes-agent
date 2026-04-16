"""
Multi-Agent Orchestrator - 多Agent调度器核心

负责：
1. 检查多Agent模式是否启用
2. 创建和管理任务
3. 根据模式路由消息
4. 调用 Agent 执行任务
5. 状态持久化
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from hermes_cli.config import load_config

from .output_parser import OutputParser, parse_classification, parse_plan, parse_review
from .event_bus import EventType, publish_event, get_event_history
from .task_workspace import TaskWorkspace

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    CREATED = "created"
    CLASSIFYING = "classifying"
    PLANNING = "planning"
    REVIEWING = "reviewing"
    DISPATCHING = "dispatching"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"              # 任务暂停（用户干预）
    CANCELLED = "cancelled"         # 任务取消
    BLOCKED = "blocked"             # 任务阻塞（等待用户确认）
    PENDING_REVIEW = "pending_review"  # 待审查（需要用户决策）


class MessageType(str, Enum):
    """消息类型"""
    CHAT = "chat"
    DECREE = "decree"


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.CREATED
    message_type: MessageType = MessageType.CHAT
    
    # 工作空间路径
    workspace_path: str = ""
    
    # 原始消息
    original_message: str = ""
    
    # 分类结果
    classification: Dict[str, Any] = field(default_factory=dict)
    
    # 规划结果
    plan: Dict[str, Any] = field(default_factory=dict)
    
    # 审议结果
    review_round: int = 0
    review_result: Dict[str, Any] = field(default_factory=dict)
    
    # 执行结果
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # 进度历史（太子汇报记录）
    progress_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 最终响应
    final_response: str = ""
    
    # 干预相关字段
    intervention_requested: bool = False       # 是否请求干预
    intervention_type: str = ""                # 干预类型: "cancel", "pause", "resume"
    intervention_reason: str = ""              # 干预原因
    intervention_at: Optional[datetime] = None # 干预时间
    intervention_by: str = ""                  # 干预操作者（用户ID）
    previous_status: Optional[TaskStatus] = None  # 暂停前的状态（用于恢复）
    
    # 阻塞相关字段
    blocked: bool = False                      # 是否被阻塞
    blocked_reason: str = ""                   # 阻塞原因
    blocked_at: Optional[datetime] = None      # 阻塞时间
    blocked_by: str = ""                       # 阻塞方（agent_id）
    blocked_context: Dict[str, Any] = field(default_factory=dict)  # 阻塞上下文（供用户决策）
    blocked_options: List[Dict[str, str]] = field(default_factory=list)  # 可选项列表
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_status(self, new_status: TaskStatus):
        """更新任务状态"""
        self.status = new_status
        self.updated_at = datetime.now()
    
    def add_progress(self, stage: str, message: str, agent: str = None):
        """添加进度记录"""
        self.progress_history.append({
            "stage": stage,
            "message": message,
            "agent": agent,
            "timestamp": datetime.now().isoformat(),
        })
    
    def request_intervention(self, intervention_type: str, reason: str = "", by: str = "") -> bool:
        """
        请求任务干预
        
        Args:
            intervention_type: 干预类型 ("cancel", "pause", "resume")
            reason: 干预原因
            by: 操作者ID
            
        Returns:
            bool: 是否成功请求干预
        """
        # 检查当前状态是否允许干预
        if self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        
        # 暂停操作：只能在运行中的状态执行
        if intervention_type == "pause":
            if self.status in (TaskStatus.CREATED, TaskStatus.PAUSED):
                return False
            self.previous_status = self.status
            
        # 恢复操作：只能在暂停状态执行
        elif intervention_type == "resume":
            if self.status != TaskStatus.PAUSED:
                return False
            if not self.previous_status:
                return False
                
        # 取消操作：可以在任何未完成状态执行
        elif intervention_type == "cancel":
            if self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
        else:
            return False
        
        self.intervention_requested = True
        self.intervention_type = intervention_type
        self.intervention_reason = reason
        self.intervention_at = datetime.now()
        self.intervention_by = by
        self.updated_at = datetime.now()
        
        return True
    
    def check_intervention(self) -> Optional[str]:
        """
        检查是否有干预请求
        
        Returns:
            Optional[str]: 返回干预类型，None表示无干预
        """
        if self.intervention_requested:
            return self.intervention_type
        return None
    
    def clear_intervention(self):
        """清除干预标记"""
        self.intervention_requested = False
        self.intervention_type = ""
        self.intervention_reason = ""
        self.intervention_at = None
        self.intervention_by = None
        self.updated_at = datetime.now()
    
    def is_cancellable(self) -> bool:
        """检查任务是否可以被取消"""
        return self.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
    
    def is_pausable(self) -> bool:
        """检查任务是否可以被暂停"""
        return self.status in (
            TaskStatus.CLASSIFYING,
            TaskStatus.PLANNING,
            TaskStatus.REVIEWING,
            TaskStatus.DISPATCHING,
            TaskStatus.EXECUTING,
        )
    
    def is_resumable(self) -> bool:
        """检查任务是否可以被恢复"""
        return self.status == TaskStatus.PAUSED and self.previous_status is not None
    
    def set_blocked(
        self,
        reason: str,
        by: str = "",
        context: Dict[str, Any] = None,
        options: List[Dict[str, str]] = None,
    ):
        """
        设置任务阻塞状态
        
        Args:
            reason: 阻塞原因
            by: 阻塞方（agent_id）
            context: 阻塞上下文信息
            options: 用户可选项列表，如 [{"id": "1", "label": "继续执行"}, {"id": "2", "label": "取消任务"}]
        """
        self.previous_status = self.status
        self.status = TaskStatus.BLOCKED
        self.blocked = True
        self.blocked_reason = reason
        self.blocked_at = datetime.now()
        self.blocked_by = by
        self.blocked_context = context or {}
        self.blocked_options = options or []
        self.updated_at = datetime.now()
    
    def clear_blocked(self, user_decision: str = ""):
        """
        清除阻塞状态，恢复到之前的状态
        
        Args:
            user_decision: 用户决策（用于记录）
        """
        if self.previous_status and self.status == TaskStatus.BLOCKED:
            self.status = self.previous_status
        self.blocked = False
        self.blocked_reason = ""
        self.blocked_at = None
        self.blocked_by = ""
        self.blocked_context = {}
        self.blocked_options = []
        self.updated_at = datetime.now()
    
    def is_blocked(self) -> bool:
        """检查任务是否被阻塞"""
        return self.status == TaskStatus.BLOCKED or self.blocked


class ProgressEvent:
    """进度事件"""
    
    # 阶段名称映射（中文显示）
    STAGE_NAMES = {
        TaskStatus.CLASSIFYING: "消息分拣",
        TaskStatus.PLANNING: "任务规划",
        TaskStatus.REVIEWING: "方案审议",
        TaskStatus.DISPATCHING: "任务派发",
        TaskStatus.EXECUTING: "任务执行",
        TaskStatus.COMPLETED: "任务完成",
        TaskStatus.FAILED: "任务失败",
        TaskStatus.PAUSED: "任务暂停",
        TaskStatus.CANCELLED: "任务取消",
        TaskStatus.BLOCKED: "任务阻塞",
        TaskStatus.PENDING_REVIEW: "待审查",
    }
    
    # Agent 名称映射（中文显示）
    AGENT_NAMES = {
        "taizi": "太子",
        "zhongshu": "中书省",
        "menxia": "门下省",
        "shangshu": "尚书省",
        "hubu": "户部",
        "libu": "礼部",
        "bingbu": "兵部",
        "xingbu": "刑部",
        "gongbu": "工部",
        "libu_hr": "吏部",
        "zaochao": "早朝官",
    }
    
    @classmethod
    def get_stage_name(cls, status: TaskStatus) -> str:
        return cls.STAGE_NAMES.get(status, status.value)
    
    @classmethod
    def get_agent_name(cls, agent_id: str) -> str:
        return cls.AGENT_NAMES.get(agent_id, agent_id)


class MultiAgentOrchestrator:
    """多Agent调度器"""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        parent_agent: Optional[Any] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """初始化调度器
        
        Args:
            config: 配置字典，如果为None则从配置文件加载
            parent_agent: 父 Agent 实例（用于 LLM 调用）
            progress_callback: 进度回调函数，接收进度事件字典
        """
        self._config = config or load_config()
        self._parent_agent = parent_agent
        self._agent_pool: Optional[Any] = None  # 延迟初始化
        self._progress_callback = progress_callback
        self._notification_callback: Optional[Callable[[Dict[str, Any]], None]] = None  # 推送通知回调
        self._state_manager: Optional[Any] = None  # 延迟初始化
        self._tasks: Dict[str, TaskContext] = {}
    
    def set_parent_agent(self, parent_agent: Any):
        """设置父 Agent"""
        self._parent_agent = parent_agent
        # 如果 AgentPool 已初始化，也更新它
        if self._agent_pool is not None:
            self._agent_pool.set_parent_agent(parent_agent)
    
    def set_progress_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]):
        """设置进度回调函数"""
        self._progress_callback = callback
    
    def set_notification_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]):
        """设置推送通知回调函数"""
        self._notification_callback = callback
    
    def _notify_progress(
        self,
        stage: TaskStatus,
        agent: Optional[str] = None,
        message: Optional[str] = None,
        task_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """发送进度通知
        
        进度默认记录到任务历史，不直接推送给用户。
        用户可通过 /tasks 命令查询任务进度。
        
        Args:
            stage: 当前阶段
            agent: 当前执行的 Agent ID
            message: 自定义消息（如果不提供则自动生成）
            task_id: 任务 ID
            extra: 额外信息
        """
        # 构建进度事件
        stage_name = ProgressEvent.get_stage_name(stage)
        agent_name = ProgressEvent.get_agent_name(agent) if agent else None
        
        # 自动生成消息
        if message is None:
            if agent_name:
                message = f"{agent_name}正在{stage_name}..."
            else:
                message = f"正在{stage_name}..."
        
        event = {
            "stage": stage.value,
            "stage_name": stage_name,
            "agent": agent,
            "agent_name": agent_name,
            "message": message,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        if extra:
            event.update(extra)
        
        # 1. 记录到任务历史（如果有当前任务）
        if task_id and task_id in self._tasks:
            task = self._tasks[task_id]
            task.add_progress(stage_name, message, agent)
        
        # 2. 记录到数据库
        try:
            state_manager = self._get_state_manager()
            state_manager.add_event(
                task_id=task_id or "unknown",
                event_type="progress",
                event_data=json.dumps(event, ensure_ascii=False),
            )
        except Exception as e:
            logger.debug(f"进度事件记录失败: {e}")
        
        # 3. 发布到事件总线
        try:
            # 映射 TaskStatus 到 EventType
            event_type_map = {
                TaskStatus.CREATED: EventType.TASK_CREATED,
                TaskStatus.CLASSIFYING: EventType.STAGE_CHANGE,
                TaskStatus.PLANNING: EventType.STAGE_CHANGE,
                TaskStatus.REVIEWING: EventType.STAGE_CHANGE,
                TaskStatus.DISPATCHING: EventType.STAGE_CHANGE,
                TaskStatus.EXECUTING: EventType.STAGE_CHANGE,
                TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
                TaskStatus.FAILED: EventType.TASK_FAILED,
            }
            
            event_type = event_type_map.get(stage, EventType.PROGRESS_UPDATE)
            
            publish_event(
                event_type=event_type,
                task_id=task_id or "unknown",
                agent_id=agent,
                payload={
                    "stage": stage.value,
                    "stage_name": stage_name,
                    "message": message,
                    **(extra or {}),
                },
            )
        except Exception as e:
            logger.debug(f"事件发布失败: {e}")
        
        # 4. 可选：推送给用户（配置控制，默认不推送）
        show_progress = self._config.get("multi_agent", {}).get("show_internal_progress", False)
        if show_progress and self._progress_callback:
            try:
                self._progress_callback(event)
            except Exception as e:
                logger.warning(f"进度回调执行失败: {e}")
        
        # 5. 关键节点推送通知
        self._send_key_stage_notification(stage, event, task_id)
    
    def _send_key_stage_notification(self, stage: TaskStatus, event: Dict[str, Any], task_id: Optional[str]):
        """发送关键节点推送通知"""
        # 检查是否启用通知
        notifications_config = self._config.get("multi_agent", {}).get("notifications", {})
        if not notifications_config.get("enabled", False):
            return
        
        # 检查是否有关键节点配置
        key_stages = notifications_config.get("key_stages", [
            "task_started",
            "review_approved", 
            "review_rejected",
            "dispatched",
            "task_completed",
            "task_failed",
        ])
        
        # 映射 TaskStatus 到通知类型
        stage_to_notification = {
            TaskStatus.CLASSIFYING: "task_started",  # 开始分类 = 任务开始
            TaskStatus.COMPLETED: "task_completed",
            TaskStatus.FAILED: "task_failed",
        }
        
        notification_type = stage_to_notification.get(stage)
        
        # 检查是否在关键节点列表中
        if not notification_type or notification_type not in key_stages:
            return
        
        # 检查是否有回调
        if not self._notification_callback:
            return
        
        # 构建通知数据
        task = self._tasks.get(task_id) if task_id else None
        
        notification_data = {
            "type": notification_type,
            "task_id": task_id,
            "title": task.title if task else "",
            "time": event.get("timestamp", ""),
            "stage": stage.value,
            "message": event.get("message", ""),
        }
        
        # 添加额外数据
        extra = event.get("extra", {})
        if extra:
            notification_data.update(extra)
        
        try:
            self._notification_callback(notification_data)
        except Exception as e:
            logger.warning(f"推送通知发送失败: {e}")
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._config
    
    @property
    def multi_agent_config(self) -> Dict[str, Any]:
        """获取多Agent配置"""
        return self._config.get("multi_agent", {})
    
    def is_enabled(self) -> bool:
        """检查是否启用多Agent模式"""
        ma_config = self.multi_agent_config
        return (
            ma_config.get("enabled", False) and 
            ma_config.get("mode", "default") == "three_provinces"
        )
    
    def get_mode(self) -> str:
        """获取当前模式"""
        return self.multi_agent_config.get("mode", "default")
    
    def _get_state_manager(self):
        """获取 StateManager 实例（延迟初始化）"""
        if self._state_manager is None:
            from .state_manager import MultiAgentStateManager
            self._state_manager = MultiAgentStateManager()
        return self._state_manager
    
    def _get_agent_pool(self):
        """获取 AgentPool 实例（延迟初始化）"""
        if self._agent_pool is None:
            from .agent_pool import AgentPool
            self._agent_pool = AgentPool(self._config, self._parent_agent)
        return self._agent_pool
    
    def create_task(self, message: str, title: str = "") -> TaskContext:
        """创建新任务
        
        Args:
            message: 用户消息
            title: 任务标题（可选）
        
        Returns:
            TaskContext: 任务上下文
        """
        task_id = f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # 初始化并创建工作空间
        workspace = TaskWorkspace(task_id)
        workspace.create()  # 创建目录结构
        workspace_path = workspace.workspace_path
        
        task = TaskContext(
            task_id=task_id,
            title=title,
            original_message=message,
            status=TaskStatus.CREATED,
            workspace_path=str(workspace_path),
        )
        
        self._tasks[task_id] = task
        
        # 保存工作空间信息到任务元数据
        task.metadata["workspace"] = {
            "path": str(workspace_path),
            "outputs_dir": str(workspace_path / "outputs"),
            "final_dir": str(workspace_path / "final"),
        }
        
        # 持久化任务
        try:
            state_manager = self._get_state_manager()
            state_manager.create_task(
                task_id=task_id,
                title=title or message[:50],
                message_type="decree",
                original_message=message,
            )
            logger.info(f"任务已持久化: {task_id}, 工作空间: {workspace_path}")
        except Exception as e:
            logger.warning(f"任务持久化失败: {e}")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[TaskContext]:
        """获取任务"""
        # 先从内存获取
        task = self._tasks.get(task_id)
        if task:
            return task
        
        # 尝试从数据库恢复
        try:
            state_manager = self._get_state_manager()
            record = state_manager.get_task(task_id)
            if record:
                task = self._record_to_context(record)
                self._tasks[task_id] = task
                return task
        except Exception as e:
            logger.warning(f"从数据库恢复任务失败: {e}")
        
        return None
    
    def _record_to_context(self, record) -> TaskContext:
        """将数据库记录转换为 TaskContext"""
        return TaskContext(
            task_id=record.task_id,
            title=record.title,
            status=TaskStatus(record.status),
            message_type=MessageType(record.message_type),
            original_message=record.original_message,
            classification=json.loads(record.classification) if record.classification else {},
            plan=json.loads(record.plan) if record.plan else {},
            review_result=json.loads(record.review_result) if record.review_result else {},
            execution_results=json.loads(record.execution_results) if record.execution_results else [],
            final_response=record.final_response,
            review_round=record.review_round,
            created_at=datetime.fromisoformat(record.created_at) if record.created_at else datetime.now(),
            updated_at=datetime.fromisoformat(record.updated_at) if record.updated_at else datetime.now(),
            metadata=json.loads(record.metadata) if record.metadata else {},
        )
    
    def _persist_task_update(self, task: TaskContext, current_agent: str = None):
        """持久化任务更新"""
        try:
            state_manager = self._get_state_manager()
            state_manager.update_task_data(
                task_id=task.task_id,
                status=task.status.value,
                current_agent=current_agent,
                title=task.title,
                classification=json.dumps(task.classification, ensure_ascii=False),
                plan=json.dumps(task.plan, ensure_ascii=False),
                review_result=json.dumps(task.review_result, ensure_ascii=False),
                execution_results=json.dumps(task.execution_results, ensure_ascii=False),
                final_response=task.final_response,
                review_round=task.review_round,
            )
        except Exception as e:
            logger.warning(f"任务更新持久化失败: {e}")
    
    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 50) -> List[TaskContext]:
        """列出任务
        
        Args:
            status: 过滤状态（可选）
            limit: 返回数量限制
        
        Returns:
            任务列表
        """
        # 优先从数据库获取
        try:
            state_manager = self._get_state_manager()
            status_filter = status.value if status else None
            records = state_manager.list_tasks(status=status_filter, limit=limit)
            return [self._record_to_context(r) for r in records]
        except Exception as e:
            logger.warning(f"从数据库获取任务列表失败: {e}")
            # 回退到内存
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            state_manager = self._get_state_manager()
            return state_manager.get_statistics()
        except Exception as e:
            logger.warning(f"获取统计信息失败: {e}")
            return {"error": str(e)}
    
    # ==================== 任务干预 ====================
    
    def check_task_intervention(self, task_id: str) -> Dict[str, Any]:
        """检查任务的干预状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            干预状态信息
        """
        state_manager = self._get_state_manager()
        return state_manager.get_intervention_status(task_id)
    
    def cancel_task(self, task_id: str, reason: str = "", by: str = "user") -> Dict[str, Any]:
        """取消任务
        
        Args:
            task_id: 任务ID
            reason: 取消原因
            by: 操作者
            
        Returns:
            操作结果
        """
        state_manager = self._get_state_manager()
        result = state_manager.cancel_task(task_id, reason, by)
        
        if result.get("success"):
            # 发布事件
            from multi_agent.event_bus import publish_event, EventType
            publish_event(
                event_type=EventType.TASK_FAILED,
                task_id=task_id,
                payload={"reason": "cancelled", "detail": reason},
            )
        
        return result
    
    def pause_task(self, task_id: str, reason: str = "", by: str = "user") -> Dict[str, Any]:
        """暂停任务
        
        Args:
            task_id: 任务ID
            reason: 暂停原因
            by: 操作者
            
        Returns:
            操作结果
        """
        state_manager = self._get_state_manager()
        result = state_manager.pause_task(task_id, reason, by)
        
        if result.get("success"):
            # 发布事件
            from multi_agent.event_bus import publish_event, EventType
            publish_event(
                event_type=EventType.STAGE_CHANGE,
                task_id=task_id,
                payload={"stage": "paused", "reason": reason},
            )
        
        return result
    
    def resume_task(self, task_id: str, by: str = "user") -> Dict[str, Any]:
        """恢复暂停的任务
        
        Args:
            task_id: 任务ID
            by: 操作者
            
        Returns:
            操作结果
        """
        state_manager = self._get_state_manager()
        result = state_manager.resume_task(task_id, by)
        
        if result.get("success"):
            # 发布事件
            from multi_agent.event_bus import publish_event, EventType
            publish_event(
                event_type=EventType.TASK_STARTED,
                task_id=task_id,
                payload={"action": "resumed"},
            )
        
        return result
    
    def _check_db_intervention(self, task_id: str) -> Optional[str]:
        """检查数据库中是否有干预请求（用于跨进程检查）
        
        Args:
            task_id: 任务ID
            
        Returns:
            干预类型或 None
        """
        try:
            state_manager = self._get_state_manager()
            task = state_manager.get_task(task_id)
            
            if task and task.status == "cancelled":
                return "cancel"
            elif task and task.status == "paused":
                return "pause"
            
            return None
        except Exception as e:
            logger.warning(f"检查干预状态失败: {e}")
            return None
    
    def _handle_intervention(self, task: TaskContext, intervention_type: str) -> str:
        """处理干预请求
        
        Args:
            task: 任务上下文
            intervention_type: 干预类型
            
        Returns:
            响应消息
        """
        if intervention_type == "cancel":
            task.update_status(TaskStatus.CANCELLED)
            task.final_response = f"任务已取消: {task.task_id}"
            self._persist_task_update(task)
            self._notify_progress(
                stage=TaskStatus.CANCELLED,
                message=f"任务已取消: {task.task_id}",
                task_id=task.task_id,
            )
            return task.final_response
            
        elif intervention_type == "pause":
            previous_status = task.status
            task.metadata["paused_from"] = previous_status.value if hasattr(previous_status, 'value') else str(previous_status)
            task.update_status(TaskStatus.PAUSED)
            self._persist_task_update(task)
            self._notify_progress(
                stage=TaskStatus.PAUSED,
                message=f"任务已暂停: {task.task_id}",
                task_id=task.task_id,
            )
            # 暂停时不返回，而是等待恢复
            return None
        
        return None
    
    # ==================== 任务阻塞 ====================
    
    def block_task(
        self,
        task_id: str,
        reason: str,
        by: str = "",
        context: Dict[str, Any] = None,
        options: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """阻塞任务，等待用户确认
        
        Args:
            task_id: 任务ID
            reason: 阻塞原因
            by: 阻塞方（agent_id）
            context: 阻塞上下文信息
            options: 用户可选项列表
            
        Returns:
            操作结果
        """
        state_manager = self._get_state_manager()
        result = state_manager.block_task(task_id, reason, by, context, options)
        
        if result.get("success"):
            # 发布事件
            from multi_agent.event_bus import publish_event, EventType
            publish_event(
                event_type=EventType.STAGE_CHANGE,
                task_id=task_id,
                payload={"stage": "blocked", "reason": reason, "options": options},
            )
        
        return result
    
    def unblock_task(
        self,
        task_id: str,
        user_decision: str = "continue",
        by: str = "user",
    ) -> Dict[str, Any]:
        """解除任务阻塞状态
        
        Args:
            task_id: 任务ID
            user_decision: 用户决策 ("continue", "cancel", 或自定义选项ID)
            by: 操作者
            
        Returns:
            操作结果
        """
        state_manager = self._get_state_manager()
        result = state_manager.unblock_task(task_id, user_decision, by)
        
        if result.get("success"):
            # 发布事件
            from multi_agent.event_bus import publish_event, EventType
            new_status = result.get("new_status", "unknown")
            if new_status == "cancelled":
                publish_event(
                    event_type=EventType.TASK_FAILED,
                    task_id=task_id,
                    payload={"reason": "user_cancelled", "decision": user_decision},
                )
            else:
                publish_event(
                    event_type=EventType.TASK_STARTED,
                    task_id=task_id,
                    payload={"action": "unblocked", "decision": user_decision},
                )
        
        return result
    
    def get_blocked_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务的阻塞状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            阻塞状态信息
        """
        state_manager = self._get_state_manager()
        return state_manager.get_blocked_status(task_id)
    
    def _check_db_block(self, task_id: str) -> Optional[Dict[str, Any]]:
        """检查数据库中是否有阻塞请求（用于跨进程检查）
        
        Args:
            task_id: 任务ID
            
        Returns:
            阻塞信息或 None
        """
        try:
            state_manager = self._get_state_manager()
            blocked_status = state_manager.get_blocked_status(task_id)
            
            if blocked_status.get("is_blocked"):
                return {
                    "blocked": True,
                    "info": blocked_status.get("blocked_info", {}),
                    "options": blocked_status.get("options", []),
                }
            
            return None
        except Exception as e:
            logger.warning(f"检查阻塞状态失败: {e}")
            return None
    
    def _handle_block(self, task: TaskContext, block_info: Dict[str, Any]) -> str:
        """处理阻塞请求
        
        Args:
            task: 任务上下文
            block_info: 阻塞信息
            
        Returns:
            响应消息
        """
        reason = block_info.get("reason", "未知原因")
        options = block_info.get("options", [])
        
        task.set_blocked(
            reason=reason,
            by=block_info.get("by", ""),
            context=block_info.get("context", {}),
            options=options,
        )
        self._persist_task_update(task)
        
        # 构建阻塞消息
        msg = f"⚠️ 任务阻塞: {task.task_id}\n\n原因: {reason}\n"
        if options:
            msg += "\n可选项:\n"
            for opt in options:
                msg += f"  [{opt.get('id', '?')}] {opt.get('label', '未知选项')}\n"
        msg += f"\n使用 `/tasks {task.task_id[:8]} confirm <选项>` 确认"
        
        self._notify_progress(
            stage=TaskStatus.BLOCKED,
            message=msg,
            task_id=task.task_id,
        )
        
        return msg
    
    # ==================== 任务归档 ====================
    
    def archive_task(self, task_id: str, result: str = "success") -> Dict[str, Any]:
        """归档任务
        
        Args:
            task_id: 任务ID
            result: 任务结果 ("success", "failed", "cancelled")
            
        Returns:
            操作结果
        """
        state_manager = self._get_state_manager()
        archive_result = state_manager.archive_task(task_id, result)
        
        if archive_result.get("success"):
            # 发布事件
            from multi_agent.event_bus import publish_event, EventType
            publish_event(
                event_type=EventType.TASK_COMPLETED,
                task_id=task_id,
                payload={"archive_id": archive_result.get("archive_id"), "result": result},
            )
        
        return archive_result
    
    def get_archive(self, archive_id: str) -> Optional[Dict[str, Any]]:
        """获取归档记录
        
        Args:
            archive_id: 归档ID
            
        Returns:
            归档记录
        """
        state_manager = self._get_state_manager()
        return state_manager.get_archive(archive_id)
    
    def list_archives(
        self,
        status: str = None,
        result: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """列出归档记录
        
        Args:
            status: 任务状态过滤
            result: 结果过滤
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制
            
        Returns:
            归档记录列表
        """
        state_manager = self._get_state_manager()
        return state_manager.list_archives(status, result, start_date, end_date, limit)
    
    def export_archive(
        self,
        archive_id: str = None,
        task_id: str = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """导出归档记录
        
        Args:
            archive_id: 归档ID
            task_id: 任务ID（二选一）
            format: 导出格式 ("json", "markdown")
            
        Returns:
            导出结果
        """
        state_manager = self._get_state_manager()
        return state_manager.export_archive(archive_id, task_id, format)
    
    def export_archives_batch(
        self,
        start_date: str = None,
        end_date: str = None,
        status: str = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """批量导出归档记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            status: 状态过滤
            format: 导出格式
            
        Returns:
            导出结果
        """
        state_manager = self._get_state_manager()
        return state_manager.export_archives_batch(start_date, end_date, status, format)
    
    def get_archive_statistics(self) -> Dict[str, Any]:
        """获取归档统计信息
        
        Returns:
            统计信息
        """
        state_manager = self._get_state_manager()
        return state_manager.get_archive_statistics()
    
    def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """处理用户消息（多Agent模式入口）
        
        Args:
            message: 用户消息
            context: 额外上下文
        
        Returns:
            响应字符串
        """
        if not self.is_enabled():
            # 未启用多Agent模式，返回提示
            return "多Agent模式未启用。使用 /mode three_provinces 启用。"
        
        # 创建任务
        task = self.create_task(message)
        
        # 通知任务开始
        self._notify_progress(
            stage=TaskStatus.CREATED,
            message="接收到任务，准备处理...",
            task_id=task.task_id,
        )
        
        try:
            # Phase 1: 消息分类（太子）
            task.update_status(TaskStatus.CLASSIFYING)
            self._persist_task_update(task, current_agent="taizi")
            self._notify_progress(
                stage=TaskStatus.CLASSIFYING,
                agent="taizi",
                task_id=task.task_id,
            )
            
            # 检查干预
            intervention = self._check_db_intervention(task.task_id)
            if intervention == "cancel":
                return self._handle_intervention(task, "cancel")
            
            classification = self._classify_message(task)
            task.classification = classification
            
            if classification.get("type") == "chat":
                # 闲聊消息，直接返回
                task.message_type = MessageType.CHAT
                task.final_response = classification.get("response", "您好！")
                task.update_status(TaskStatus.COMPLETED)
                self._persist_task_update(task)
                self._notify_progress(
                    stage=TaskStatus.COMPLETED,
                    message="闲聊消息，已直接回复",
                    task_id=task.task_id,
                )
                return task.final_response
            
            # 旨意消息，进入三省六部流程
            task.message_type = MessageType.DECREE
            task.title = classification.get("title", task.title)
            task.description = classification.get("description", task.original_message)
            
            # 检查干预
            intervention = self._check_db_intervention(task.task_id)
            if intervention == "cancel":
                return self._handle_intervention(task, "cancel")
            
            # Phase 2: 规划（中书省）
            task.update_status(TaskStatus.PLANNING)
            self._persist_task_update(task, current_agent="zhongshu")
            self._notify_progress(
                stage=TaskStatus.PLANNING,
                agent="zhongshu",
                task_id=task.task_id,
                extra={"title": task.title},
            )
            
            plan = self._plan_task(task)
            task.plan = plan
            
            # 检查干预
            intervention = self._check_db_intervention(task.task_id)
            if intervention == "cancel":
                return self._handle_intervention(task, "cancel")
            elif intervention == "pause":
                response = self._handle_intervention(task, "pause")
                if response:
                    return response
            
            # Phase 3: 审议循环（门下省）
            task.update_status(TaskStatus.REVIEWING)
            self._persist_task_update(task, current_agent="menxia")
            self._notify_progress(
                stage=TaskStatus.REVIEWING,
                agent="menxia",
                task_id=task.task_id,
            )
            
            review_result = self._review_plan(task)
            task.review_result = review_result
            
            # 检查干预
            intervention = self._check_db_intervention(task.task_id)
            if intervention == "cancel":
                return self._handle_intervention(task, "cancel")
            elif intervention == "pause":
                response = self._handle_intervention(task, "pause")
                if response:
                    return response
            
            # Phase 4: 执行派发（尚书省）
            if review_result.get("decision") == "approved":
                task.update_status(TaskStatus.DISPATCHING)
                self._persist_task_update(task, current_agent="shangshu")
                self._notify_progress(
                    stage=TaskStatus.DISPATCHING,
                    agent="shangshu",
                    task_id=task.task_id,
                    extra={"plan_summary": plan.get("summary", "")},
                )
                
                # 执行前最终检查干预
                intervention = self._check_db_intervention(task.task_id)
                if intervention == "cancel":
                    return self._handle_intervention(task, "cancel")
                elif intervention == "pause":
                    response = self._handle_intervention(task, "pause")
                    if response:
                        return response
                
                execution_results = self._execute_plan(task)
                task.execution_results = execution_results
            else:
                # 封驳，需要重新规划
                self._notify_progress(
                    stage=TaskStatus.REVIEWING,
                    agent="menxia",
                    message=f"门下省封驳：{review_result.get('reason', '方案需要调整')}",
                    task_id=task.task_id,
                )
            
            # 生成最终响应（太子汇总）
            self._notify_progress(
                stage=TaskStatus.EXECUTING,
                agent="taizi",
                message="太子正在汇总结果，准备回复...",
                task_id=task.task_id,
            )
            task.final_response = self._generate_final_response(task)
            task.update_status(TaskStatus.COMPLETED)
            self._persist_task_update(task)
            self._notify_progress(
                stage=TaskStatus.COMPLETED,
                agent="taizi",
                message="太子已完成汇报",
                task_id=task.task_id,
            )
            
            return task.final_response
        
        except Exception as e:
            task.update_status(TaskStatus.FAILED)
            task.metadata["error"] = str(e)
            self._persist_task_update(task)
            self._notify_progress(
                stage=TaskStatus.FAILED,
                message=f"任务执行失败: {e}",
                task_id=task.task_id,
            )
            return f"任务执行失败: {e}"
    
    def _classify_message(self, task: TaskContext) -> Dict[str, Any]:
        """分类消息（太子）"""
        agent_pool = self._get_agent_pool()
        
        # 调用太子进行分类
        result = agent_pool.execute(
            agent_id="taizi",
            task_id=task.task_id,
            input_data=task.original_message,
            context={"action": "classify"},
            workspace_path=task.workspace_path,
        )
        
        # 使用 OutputParser 解析结果
        result_str = result if isinstance(result, str) else json.dumps(result)
        parse_result = parse_classification(result_str)
        
        if parse_result.success and parse_result.model:
            # 解析成功，返回模型数据
            data = parse_result.model.model_dump()
            if parse_result.fixes_applied:
                logger.info(f"Classification auto-fixed: {parse_result.fixes_applied}")
            return data
        
        # 解析失败，使用智能提取作为后备
        logger.warning(f"Classification parse failed: {parse_result.error}, using smart extraction")
        
        # 智能判断类型
        result_lower = result_str.lower()
        if any(kw in result_lower for kw in ["闲聊", "chat", "问候", "寒暄", "greeting"]):
            return {
                "type": "chat",
                "response": "您好！我是太子，很高兴为您服务～"
            }
        
        # 默认作为旨意处理
        return {
            "type": "decree",
            "title": task.original_message[:50],
            "description": task.original_message,
            "category": "其他",
            "urgency": "中",
            "complexity": "中等",
            "suggested_agents": ["工部"],
        }
    
    def _plan_task(self, task: TaskContext) -> Dict[str, Any]:
        """规划任务（中书省）"""
        agent_pool = self._get_agent_pool()
        
        # 调用中书省进行规划
        result = agent_pool.execute(
            agent_id="zhongshu",
            task_id=task.task_id,
            input_data=json.dumps({
                "title": task.title,
                "description": task.description,
                "classification": task.classification,
            }),
            context={"action": "plan"},
            workspace_path=task.workspace_path,
        )
        
        # 使用 OutputParser 解析结果
        result_str = result if isinstance(result, str) else json.dumps(result)
        parse_result = parse_plan(result_str)
        
        if parse_result.success and parse_result.model:
            data = parse_result.model.model_dump()
            if parse_result.fixes_applied:
                logger.info(f"Plan auto-fixed: {parse_result.fixes_applied}")
            return data
        
        # 解析失败，尝试基础 JSON 解析
        logger.warning(f"Plan parse failed: {parse_result.error}")
        try:
            return json.loads(result_str)
        except json.JSONDecodeError:
            return {"phases": [], "steps": [], "error": "规划解析失败"}
    
    def _review_plan(self, task: TaskContext) -> Dict[str, Any]:
        """审议方案（门下省）"""
        agent_pool = self._get_agent_pool()
        
        # 获取最大审议轮数
        max_rounds = self.multi_agent_config.get("workflow", {}).get("max_review_rounds", 3)
        
        for round_num in range(1, max_rounds + 1):
            task.review_round = round_num
            
            # 调用门下省审议
            result = agent_pool.execute(
                agent_id="menxia",
                task_id=task.task_id,
                input_data=json.dumps({
                    "plan": task.plan,
                    "round": round_num,
                    "max_rounds": max_rounds,
                }),
                context={"action": "review"},
                workspace_path=task.workspace_path,
            )
            
            # 使用 OutputParser 解析结果
            result_str = result if isinstance(result, str) else json.dumps(result)
            parse_result = parse_review(result_str)
            
            if parse_result.success and parse_result.model:
                review = parse_result.model.model_dump()
                if parse_result.fixes_applied:
                    logger.info(f"Review auto-fixed: {parse_result.fixes_applied}")
            else:
                # 解析失败，尝试基础 JSON 解析
                logger.warning(f"Review parse failed: {parse_result.error}")
                try:
                    review = json.loads(result_str)
                except json.JSONDecodeError:
                    logger.warning(f"审议结果解析失败: {result_str[:100]}")
                    continue
            
            # 检查是否通过
            if review.get("decision") == "approved":
                return review
            
            # 最后一轮强制通过
            if round_num == max_rounds:
                auto_approve = self.multi_agent_config.get("workflow", {}).get("auto_approve_final", True)
                if auto_approve:
                    return {"decision": "approved", "reason": "最后一轮强制通过"}
            
            # 封驳，修改方案后重试
            task.review_round = round_num
            task.review_result = review
            
            # 调用中书省修改方案
            revised_plan = self._revise_plan(task, review)
            if revised_plan:
                task.plan = revised_plan
                logger.info(f"中书省根据审议意见修改方案 (第{round_num}轮)")
            else:
                # 修改失败，继续下一轮
                logger.warning(f"方案修改失败，继续第{round_num+1}轮审议")
        
        return {"decision": "approved", "reason": "审议完成"}
    
    def _revise_plan(self, task: TaskContext, review: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """根据审议意见修改方案
        
        Args:
            task: 任务上下文
            review: 审议结果（包含封驳意见）
        
        Returns:
            修改后的方案，失败返回None
        """
        agent_pool = self._get_agent_pool()
        
        # 提取审议意见
        review_comments = review.get("comments", [])
        review_issues = review.get("issues", [])
        review_suggestions = review.get("suggestions", [])
        scores = review.get("scores", {})
        
        # 构建修改请求
        revise_request = {
            "original_plan": task.plan,
            "review_result": {
                "decision": review.get("decision"),
                "scores": scores,
                "comments": review_comments,
                "issues": review_issues,
                "suggestions": review_suggestions,
            },
            "round": task.review_round,
            "task_title": task.title,
            "task_description": task.description,
        }
        
        # 调用中书省修改方案
        result = agent_pool.execute(
            agent_id="zhongshu",
            task_id=f"{task.task_id}-revise-{task.review_round}",
            input_data=json.dumps(revise_request, ensure_ascii=False),
            context={"action": "revise"},
            workspace_path=task.workspace_path,
        )
        
        # 解析修改后的方案
        try:
            if isinstance(result, str):
                revised = json.loads(result)
            else:
                revised = result
            
            # 提取新方案
            if isinstance(revised, dict):
                if revised.get("plan"):
                    return revised["plan"]
                if revised.get("revised_plan"):
                    return revised["revised_plan"]
                # 如果返回本身就是方案
                if revised.get("steps") or revised.get("analysis"):
                    return revised
            
            return None
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"方案修改结果解析失败: {e}")
            return None
    
    def _execute_plan(self, task: TaskContext) -> List[Dict[str, Any]]:
        """执行方案（尚书省）"""
        agent_pool = self._get_agent_pool()
        
        # 调用尚书省进行派发决策
        dispatch_decision = agent_pool.execute(
            agent_id="shangshu",
            task_id=task.task_id,
            input_data=json.dumps({
                "plan": task.plan,
                "classification": task.classification,
                "title": task.title,
                "description": task.description,
            }),
            context={"action": "dispatch"},
            workspace_path=task.workspace_path,
        )
        
        # 解析派发决策
        dispatches = self._parse_dispatch_decision(dispatch_decision)
        
        if not dispatches:
            # 没有派发任务，返回决策本身
            return [{"summary": dispatch_decision[:500] if isinstance(dispatch_decision, str) else str(dispatch_decision)}]
        
        # 执行派发 - 调用六部
        results = []
        for dispatch in dispatches:
            to_agent = dispatch.get("agent", "gongbu")
            subtask = dispatch.get("task", "")
            priority = dispatch.get("priority", "medium")
            
            logger.info(f"尚书省 -> {to_agent}: {subtask[:50]}...")
            
            # 通过Agent池派发任务
            result = agent_pool.dispatch_to_agent(
                from_agent="shangshu",
                to_agent=to_agent,
                task=subtask,
                task_id=f"{task.task_id}-{to_agent}",
                context={"priority": priority, "parent_task": task.title},
                workspace_path=task.workspace_path,
            )
            
            results.append({
                "agent": to_agent,
                "task": subtask,
                "result": result,
                "status": "completed" if not self._has_error(result) else "failed",
            })
        
        return results
    
    def _parse_dispatch_decision(self, decision: Any) -> List[Dict[str, str]]:
        """解析尚书省的派发决策"""
        if isinstance(decision, dict):
            dispatches = decision.get("dispatches", [])
            if dispatches:
                return dispatches
            # 兼容其他格式
            if decision.get("agent"):
                return [decision]
            return []
        
        if isinstance(decision, str):
            try:
                parsed = json.loads(decision)
                return self._parse_dispatch_decision(parsed)
            except json.JSONDecodeError:
                # 尝试提取JSON
                import re
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', decision)
                if json_match:
                    try:
                        return json.loads(json_match.group(1)).get("dispatches", [])
                    except:
                        pass
                # 尝试提取 dispatches 字段
                match = re.search(r'"dispatches"\s*:\s*\[([\s\S]*?)\]', decision)
                if match:
                    try:
                        dispatches = json.loads("[" + match.group(1) + "]")
                        return dispatches
                    except:
                        pass
        return []
    
    def _has_error(self, result: Any) -> bool:
        """检查结果是否包含错误"""
        if isinstance(result, dict):
            return result.get("error") is not None
        if isinstance(result, str):
            return '"error"' in result and 'success": false' in result.lower()
        return False
    
    def _taizi_summarize(self, task: TaskContext) -> str:
        """太子汇总结果并生成最终响应
        
        这是三省六部架构的核心：太子是唯一的消息入口和出口。
        所有子Agent的执行结果都汇总到太子，由太子生成最终响应返回给用户。
        """
        agent_pool = self._get_agent_pool()
        
        # 构建汇总提示
        summary_prompt = f"""你是「太子」，现在需要汇总三省六部的执行结果，向用户汇报。

## 原始旨意
{task.original_message}

## 任务信息
- 标题: {task.title}
- 类型: {task.message_type.value}
- 状态: {task.status.value}

## 中书省规划
{json.dumps(task.plan, ensure_ascii=False, indent=2) if task.plan else '无'}

## 门下省审议
{json.dumps(task.review_result, ensure_ascii=False, indent=2) if task.review_result else '无'}

## 执行结果
{json.dumps(task.execution_results, ensure_ascii=False, indent=2) if task.execution_results else '无'}

## 你的任务
请用清晰、友好的语言向用户汇报：
1. 任务完成情况
2. 主要执行结果（如果有关键输出）
3. 后续建议（如果有）

注意：
- 不要暴露内部Agent的工作细节
- 用用户能理解的语言表达
- 保持简洁，突出重点
- 如果执行失败，说明原因和建议
"""
        
        # 调用太子生成最终响应
        self._notify_progress(
            stage=TaskStatus.EXECUTING,
            agent="taizi",
            message="太子正在汇总结果...",
            task_id=task.task_id,
        )
        
        result = agent_pool.execute(
            agent_id="taizi",
            task_id=task.task_id,
            input_data=summary_prompt,
            context={"action": "summarize"},
            workspace_path=task.workspace_path,
        )
        
        # 解析结果
        if isinstance(result, dict):
            return result.get("response", result.get("output", str(result)))
        elif isinstance(result, str):
            # 尝试解析JSON
            try:
                parsed = json.loads(result)
                return parsed.get("response", parsed.get("output", result))
            except:
                return result
        else:
            return str(result)

    def _generate_final_response(self, task: TaskContext) -> str:
        """生成最终响应（通过太子汇总）"""
        if task.message_type == MessageType.CHAT:
            return task.final_response
        
        # 通过太子汇总结果
        return self._taizi_summarize(task)


def is_multi_agent_enabled() -> bool:
    """检查是否启用多Agent模式（便捷函数）"""
    orchestrator = MultiAgentOrchestrator()
    return orchestrator.is_enabled()
