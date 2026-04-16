"""
Event Bus - 事件总线

负责：
1. 事件发布/订阅
2. 支持异步执行
3. 实时进度推送
4. 事件历史查询

对齐 Edict 的 Redis Streams 设计，先实现内存版本
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型"""
    # 任务生命周期
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # Agent 调用
    AGENT_CALLED = "agent.called"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    
    # 阶段变更
    STAGE_CHANGE = "stage.change"
    
    # 进度更新
    PROGRESS_UPDATE = "progress.update"
    
    # 审计事件
    AUDIT_LOG = "audit.log"
    
    # 熔断器事件
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker.tripped"
    CIRCUIT_BREAKER_RECOVERED = "circuit_breaker.recovered"


@dataclass
class Event:
    """事件"""
    event_id: str
    event_type: EventType
    task_id: str
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建"""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            task_id=data["task_id"],
            agent_id=data.get("agent_id"),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


# 回调函数类型
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]  # 可以是协程


class EventBus(ABC):
    """事件总线基类"""
    
    @abstractmethod
    def publish(self, event: Event) -> None:
        """发布事件"""
        pass
    
    @abstractmethod
    def subscribe(
        self,
        event_type: EventType,
        handler: Union[EventHandler, AsyncEventHandler],
    ) -> str:
        """订阅事件
        
        Args:
            event_type: 事件类型
            handler: 处理函数（同步或异步）
            
        Returns:
            订阅ID，用于取消订阅
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅
        
        Args:
            subscription_id: 订阅ID
            
        Returns:
            是否成功取消
        """
        pass
    
    @abstractmethod
    def get_history(
        self,
        task_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> List[Event]:
        """获取事件历史"""
        pass


class InMemoryEventBus(EventBus):
    """内存事件总线
    
    特点：
    1. 同步调用订阅者（简单可靠）
    2. 线程安全
    3. 支持事件历史
    """
    
    def __init__(self, max_history: int = 1000):
        """初始化
        
        Args:
            max_history: 最大历史事件数量
        """
        self._subscribers: Dict[EventType, Dict[str, Union[EventHandler, AsyncEventHandler]]] = {}
        self._event_history: List[Event] = []
        self._max_history = max_history
        self._lock = threading.Lock()
        
        # 统计
        self._total_published = 0
        self._total_delivered = 0
    
    def publish(self, event: Event) -> None:
        """发布事件"""
        with self._lock:
            # 记录历史
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
            
            # 获取订阅者
            handlers = self._subscribers.get(event.event_type, {}).copy()
        
        self._total_published += 1
        
        # 通知订阅者（在锁外执行，避免死锁）
        for handler_id, handler in handlers.items():
            try:
                result = handler(event)
                # 检查是否是协程
                if asyncio.iscoroutine(result):
                    # 在后台运行协程
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(result)
                        else:
                            loop.run_until_complete(result)
                    except RuntimeError:
                        # 没有事件循环，创建新的
                        asyncio.run(result)
                self._total_delivered += 1
            except Exception as e:
                logger.error(f"Event handler {handler_id} failed: {e}")
        
        logger.debug(
            f"Event published: {event.event_type.value} for task {event.task_id}, "
            f"delivered to {len(handlers)} handlers"
        )
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Union[EventHandler, AsyncEventHandler],
    ) -> str:
        """订阅事件"""
        subscription_id = str(uuid.uuid4())[:8]
        
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = {}
            self._subscribers[event_type][subscription_id] = handler
        
        logger.debug(f"Subscribed to {event_type.value}: {subscription_id}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        with self._lock:
            for event_type, handlers in self._subscribers.items():
                if subscription_id in handlers:
                    del handlers[subscription_id]
                    logger.debug(f"Unsubscribed: {subscription_id}")
                    return True
        return False
    
    def get_history(
        self,
        task_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> List[Event]:
        """获取事件历史"""
        with self._lock:
            events = list(self._event_history)
        
        # 过滤
        if task_id:
            events = [e for e in events if e.task_id == task_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # 返回最近的 N 条
        return events[-limit:]
    
    def clear_history(self) -> None:
        """清空历史"""
        with self._lock:
            self._event_history.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "total_published": self._total_published,
                "total_delivered": self._total_delivered,
                "history_count": len(self._event_history),
                "subscriber_count": sum(
                    len(handlers) for handlers in self._subscribers.values()
                ),
            }
    
    def subscribe_all(
        self,
        handler: Union[EventHandler, AsyncEventHandler],
        event_types: Optional[List[EventType]] = None,
    ) -> List[str]:
        """订阅多个事件类型
        
        Args:
            handler: 处理函数
            event_types: 事件类型列表，None 表示订阅所有
            
        Returns:
            订阅ID列表
        """
        if event_types is None:
            event_types = list(EventType)
        
        subscription_ids = []
        for event_type in event_types:
            sub_id = self.subscribe(event_type, handler)
            subscription_ids.append(sub_id)
        
        return subscription_ids


# ============================================================================
# 全局事件总线实例
# ============================================================================

_event_bus: Optional[EventBus] = None
_event_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _event_bus
    with _event_bus_lock:
        if _event_bus is None:
            _event_bus = InMemoryEventBus()
        return _event_bus


def set_event_bus(bus: EventBus) -> None:
    """设置全局事件总线"""
    global _event_bus
    with _event_bus_lock:
        _event_bus = bus


def reset_event_bus() -> None:
    """重置全局事件总线"""
    global _event_bus
    with _event_bus_lock:
        _event_bus = None


# ============================================================================
# 便捷函数
# ============================================================================

def publish_event(
    event_type: EventType,
    task_id: str,
    agent_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Event:
    """发布事件的便捷函数
    
    Args:
        event_type: 事件类型
        task_id: 任务ID
        agent_id: Agent ID
        payload: 事件数据
        
    Returns:
        创建的事件对象
    """
    event = Event(
        event_id=str(uuid.uuid4())[:12],
        event_type=event_type,
        task_id=task_id,
        agent_id=agent_id,
        payload=payload or {},
    )
    get_event_bus().publish(event)
    return event


def subscribe_to_event(
    event_type: EventType,
    handler: Union[EventHandler, AsyncEventHandler],
) -> str:
    """订阅事件的便捷函数"""
    return get_event_bus().subscribe(event_type, handler)


def unsubscribe_from_event(subscription_id: str) -> bool:
    """取消订阅的便捷函数"""
    return get_event_bus().unsubscribe(subscription_id)


def get_event_history(
    task_id: Optional[str] = None,
    event_type: Optional[EventType] = None,
    limit: int = 100,
) -> List[Event]:
    """获取事件历史的便捷函数"""
    return get_event_bus().get_history(task_id, event_type, limit)


# ============================================================================
# 事件发布器 Mixin
# ============================================================================

class EventPublisher:
    """事件发布器 Mixin
    
    为类提供便捷的事件发布方法
    """
    
    def _publish_event(
        self,
        event_type: EventType,
        task_id: str,
        agent_id: Optional[str] = None,
        **kwargs,
    ) -> Event:
        """发布事件"""
        return publish_event(
            event_type=event_type,
            task_id=task_id,
            agent_id=agent_id,
            payload=kwargs if kwargs else None,
        )
