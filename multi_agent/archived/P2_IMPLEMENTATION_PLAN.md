# 三省六部多Agent系统 - P2实施落地计划

> 版本: v1.0
> 日期: 2026-04-16
> 状态: 待实施

---

## 一、P2功能概览

| ID | 功能 | 工时 | 优先级 | 依赖 |
|----|------|------|--------|------|
| P2-1 | 事件总线（内存版） | 4h | 高 | 无 |
| P2-2 | 错误处理增强 | 3h | 高 | 无 |
| P2-3 | 审计日志 | 2h | 中 | P1-1（已完成） |
| P2-4 | 输出解析增强 | 3h | 中 | 无 |

**总工时: 12h**

---

## 二、实施顺序

```
第1步: P2-3 审计日志 (2h)
  │
  ├─ 原因: 基础设施，其他功能可复用
  └─ 产出: 操作记录、问题追溯

第2步: P2-4 输出解析增强 (3h)
  │
  ├─ 原因: 提升稳定性，减少LLM输出解析错误
  └─ 产出: Schema验证、容错解析

第3步: P2-2 错误处理增强 (3h)
  │
  ├─ 原因: 提升健壮性，智能重试和熔断
  └─ 产出: RetryPolicy、CircuitBreaker

第4步: P2-1 事件总线 (4h)
  │
  ├─ 原因: 支持异步执行、并行任务
  └─ 产出: InMemoryEventBus、事件订阅
```

---

## 三、P2-3 审计日志 (2h)

### 3.1 目标

- 详细记录每个Agent的输入输出
- 支持操作追溯和问题定位
- 满足企业合规审计需求

### 3.2 实现方案

#### 3.2.1 数据库表扩展

```sql
-- ma_agent_runs 表扩展
ALTER TABLE ma_agent_runs ADD COLUMN tokens_input INTEGER DEFAULT 0;
ALTER TABLE ma_agent_runs ADD COLUMN tokens_output INTEGER DEFAULT 0;
ALTER TABLE ma_agent_runs ADD COLUMN latency_ms INTEGER DEFAULT 0;
ALTER TABLE ma_agent_runs ADD COLUMN model_version TEXT;

-- 新增审计日志表
CREATE TABLE ma_audit_log (
    log_id TEXT PRIMARY KEY,
    task_id TEXT,
    agent_id TEXT,
    action TEXT,           -- 'call', 'dispatch', 'review', 'execute'
    input_summary TEXT,    -- 输入摘要（前500字符）
    output_summary TEXT,   -- 输出摘要（前500字符）
    status TEXT,           -- 'success', 'failed', 'timeout'
    error_message TEXT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES ma_tasks(task_id)
);
```

#### 3.2.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `state_manager.py` | 添加 `add_audit_log()`, `get_audit_logs()` 方法 |
| `agent_pool.py` | 在 `_execute_with_llm()` 中记录审计日志 |
| `orchestrator.py` | 在关键节点记录审计事件 |

#### 3.2.3 API接口

```python
class MultiAgentStateManager:
    def add_audit_log(
        self,
        task_id: str,
        agent_id: str,
        action: str,
        input_summary: str,
        output_summary: str = "",
        status: str = "success",
        error_message: str = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
    ) -> str:
        """添加审计日志"""
        pass
    
    def get_audit_logs(
        self,
        task_id: str = None,
        agent_id: str = None,
        action: str = None,
        limit: int = 100,
    ) -> List[Dict]:
        """查询审计日志"""
        pass
    
    def export_audit_logs(
        self,
        task_id: str = None,
        format: str = "json",  # json, csv
        start_time: str = None,
        end_time: str = None,
    ) -> str:
        """导出审计日志"""
        pass
```

### 3.3 验收标准

- [ ] 审计日志表创建成功
- [ ] Agent调用自动记录审计日志
- [ ] 支持按任务/Agent/操作类型查询
- [ ] 支持JSON/CSV导出
- [ ] CLI命令: `/tasks <id> audit` 查看审计日志

---

## 四、P2-4 输出解析增强 (3h)

### 4.1 目标

- 使用Pydantic定义输出Schema
- 强制JSON格式输出
- 多格式容错解析

### 4.2 实现方案

#### 4.2.1 新建文件

**`multi_agent/output_schemas.py`**

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum

class MessageType(str, Enum):
    CHAT = "chat"
    DECREE = "decree"

class ClassificationOutput(BaseModel):
    """太子分类输出"""
    type: MessageType
    response: Optional[str] = None  # 闲聊回复
    title: Optional[str] = None     # 旨意标题
    description: Optional[str] = None
    category: Optional[str] = None
    urgency: Optional[Literal["低", "中", "高", "紧急"]] = None
    complexity: Optional[Literal["简单", "中等", "复杂"]] = None
    suggested_agents: Optional[List[str]] = None

class PlanStep(BaseModel):
    """规划步骤"""
    step: int
    action: str
    agent: str
    dependencies: List[int] = []
    estimated_time: Optional[str] = None

class PlanOutput(BaseModel):
    """中书省规划输出"""
    analysis: str
    steps: List[PlanStep]
    resources: List[str] = []
    risks: List[str] = []
    estimated_total_time: Optional[str] = None

class ReviewScore(BaseModel):
    """审议评分"""
    feasibility: int = Field(ge=0, le=10)
    completeness: int = Field(ge=0, le=10)
    risk_management: int = Field(ge=0, le=10)
    resource_allocation: int = Field(ge=0, le=10)

class ReviewOutput(BaseModel):
    """门下省审议输出"""
    decision: Literal["approved", "rejected"]
    scores: Optional[ReviewScore] = None
    total_score: Optional[int] = None
    comments: Optional[str] = None
    issues: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None

class DispatchItem(BaseModel):
    """派发项"""
    agent: str
    task: str
    priority: Literal["high", "medium", "low"] = "medium"
    dependencies: List[str] = []

class DispatchOutput(BaseModel):
    """尚书省派发输出"""
    dispatches: List[DispatchItem]
    execution_order: List[str] = []
    parallel_groups: List[List[str]] = []
```

#### 4.2.2 解析器

**`multi_agent/output_parser.py`**

```python
import json
import re
import yaml
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar('T', bound=BaseModel)

class OutputParser:
    """LLM输出解析器"""
    
    @staticmethod
    def parse_json(text: str) -> Optional[Dict]:
        """解析JSON（多种格式）"""
        # 1. 直接解析
        try:
            return json.loads(text)
        except:
            pass
        
        # 2. 提取 ```json 代码块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # 3. 提取花括号内容
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return None
    
    @staticmethod
    def parse_yaml(text: str) -> Optional[Dict]:
        """解析YAML"""
        try:
            return yaml.safe_load(text)
        except:
            return None
    
    @classmethod
    def parse_to_model(cls, text: str, model_class: Type[T]) -> Optional[T]:
        """解析到Pydantic模型"""
        data = cls.parse_json(text) or cls.parse_yaml(text)
        if data:
            try:
                return model_class(**data)
            except ValidationError as e:
                # 尝试修复常见错误
                fixed_data = cls._auto_fix(data, model_class)
                if fixed_data:
                    try:
                        return model_class(**fixed_data)
                    except:
                        pass
        return None
    
    @staticmethod
    def _auto_fix(data: Dict, model_class: Type[T]) -> Optional[Dict]:
        """自动修复常见错误"""
        # TODO: 实现智能修复逻辑
        # - 字段名映射（如 "agent_id" -> "agent"）
        # - 类型转换（如字符串转数字）
        # - 默认值填充
        return data
```

#### 4.2.3 修改文件

| 文件 | 修改内容 |
|------|----------|
| `orchestrator.py` | 使用 `OutputParser.parse_to_model()` 解析输出 |
| `agent_pool.py` | 添加输出格式提示到system prompt |

### 4.3 验收标准

- [ ] Pydantic模型定义完整
- [ ] 支持JSON/YAML/文本格式解析
- [ ] 解析失败时有容错处理
- [ ] 各Agent输出符合Schema

---

## 五、P2-2 错误处理增强 (3h)

### 5.1 目标

- 智能重试：LLM调用失败自动重试
- 熔断机制：连续失败后降级处理
- 优雅降级：单个Agent失败不影响整体

### 5.2 实现方案

#### 5.2.1 新建文件

**`multi_agent/error_handler.py`**

```python
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Any, List
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开（尝试恢复）

@dataclass
class RetryPolicy:
    """重试策略"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout", "rate_limit", "server_error", "connection_error"
    ])
    
    def get_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避）"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)
    
    def should_retry(self, error: str) -> bool:
        """判断是否应该重试"""
        return any(e in error.lower() for e in self.retryable_errors)

@dataclass
class CircuitBreaker:
    """熔断器"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0
    
    def record_success(self):
        """记录成功"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
                return True
            return False
        
        # HALF_OPEN: 允许一次尝试
        return True

class ErrorHandler:
    """错误处理器"""
    
    def __init__(
        self,
        retry_policy: RetryPolicy = None,
        circuit_breaker: CircuitBreaker = None,
        fallback: Callable = None,
    ):
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.fallback = fallback
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.retry_policy.max_attempts):
            # 检查熔断器
            if not self.circuit_breaker.can_execute():
                if self.fallback:
                    logger.warning("Circuit breaker OPEN, using fallback")
                    return self.fallback(*args, **kwargs)
                raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result
            
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                if self.retry_policy.should_retry(error_str):
                    delay = self.retry_policy.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {error_str}, "
                        f"retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                else:
                    # 不可重试的错误
                    self.circuit_breaker.record_failure()
                    raise
        
        # 所有重试失败
        self.circuit_breaker.record_failure()
        
        if self.fallback:
            logger.warning(f"All {self.retry_policy.max_attempts} attempts failed, using fallback")
            return self.fallback(*args, **kwargs)
        
        raise last_error

def with_retry(
    max_attempts: int = 3,
    retryable_errors: List[str] = None,
    fallback: Callable = None,
):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler(
                retry_policy=RetryPolicy(
                    max_attempts=max_attempts,
                    retryable_errors=retryable_errors or ["timeout", "rate_limit"],
                ),
                fallback=fallback,
            )
            return handler.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator
```

#### 5.2.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `agent_pool.py` | 使用 `ErrorHandler` 包装LLM调用 |
| `orchestrator.py` | 添加Agent级别的熔断器 |

#### 5.2.3 配置扩展

**`config.yaml`**

```yaml
multi_agent:
  error_handling:
    retry:
      max_attempts: 3
      base_delay: 1.0
      max_delay: 30.0
      retryable_errors:
        - timeout
        - rate_limit
        - server_error
        - connection_error
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 60.0
    fallback_enabled: true
```

### 5.3 验收标准

- [ ] 重试策略实现（指数退避）
- [ ] 熔断器实现（CLOSED/OPEN/HALF_OPEN）
- [ ] Fallback降级机制
- [ ] 配置项支持
- [ ] 单元测试覆盖

---

## 六、P2-1 事件总线 (4h)

### 6.1 目标

- 支持异步执行
- 支持并行任务处理
- 实时进度推送

### 6.2 实现方案

#### 6.2.1 新建文件

**`multi_agent/event_bus.py`**

```python
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Any, Optional
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    """事件类型"""
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    AGENT_CALLED = "agent.called"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    
    PROGRESS_UPDATE = "progress.update"
    STAGE_CHANGE = "stage.change"

@dataclass
class Event:
    """事件"""
    event_id: str
    event_type: EventType
    task_id: str
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Event":
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            task_id=data["task_id"],
            agent_id=data.get("agent_id"),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp"),
        )

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
        handler: Callable[[Event], None],
    ) -> str:
        """订阅事件"""
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        pass

class InMemoryEventBus(EventBus):
    """内存事件总线"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, Dict[str, Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def publish(self, event: Event) -> None:
        """发布事件"""
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # 通知订阅者
        handlers = self._subscribers.get(event.event_type, {})
        for handler_id, handler in handlers.items():
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler {handler_id} failed: {e}")
        
        logger.debug(f"Event published: {event.event_type.value} for task {event.task_id}")
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> str:
        """订阅事件"""
        subscription_id = str(uuid.uuid4())
        
        if event_type not in self._subscribers:
            self._subscribers[event_type] = {}
        
        self._subscribers[event_type][subscription_id] = handler
        logger.debug(f"Subscribed to {event_type.value}: {subscription_id}")
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        for event_type, handlers in self._subscribers.items():
            if subscription_id in handlers:
                del handlers[subscription_id]
                logger.debug(f"Unsubscribed: {subscription_id}")
                return
    
    def get_history(
        self,
        task_id: str = None,
        event_type: EventType = None,
        limit: int = 100,
    ) -> List[Event]:
        """获取事件历史"""
        events = self._event_history
        
        if task_id:
            events = [e for e in events if e.task_id == task_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]

# 全局事件总线实例
_event_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _event_bus
    if _event_bus is None:
        _event_bus = InMemoryEventBus()
    return _event_bus

def set_event_bus(bus: EventBus) -> None:
    """设置全局事件总线"""
    global _event_bus
    _event_bus = bus

def publish_event(
    event_type: EventType,
    task_id: str,
    agent_id: str = None,
    payload: Dict = None,
) -> Event:
    """发布事件的便捷函数"""
    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        task_id=task_id,
        agent_id=agent_id,
        payload=payload or {},
    )
    get_event_bus().publish(event)
    return event
```

#### 6.2.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `orchestrator.py` | 使用事件总线发布进度事件 |
| `agent_pool.py` | 发布Agent调用事件 |
| `__init__.py` | 导出EventBus相关类 |

#### 6.2.3 配置扩展

```yaml
multi_agent:
  event_bus:
    type: memory  # memory | redis
    max_history: 1000
    redis_url: ""  # Redis模式需要
```

### 6.3 验收标准

- [ ] InMemoryEventBus实现完成
- [ ] 事件发布/订阅正常工作
- [ ] 与现有进度通知集成
- [ ] 支持事件历史查询
- [ ] 可扩展为Redis实现

---

## 七、测试计划

### 7.1 单元测试

| 模块 | 测试文件 | 覆盖内容 |
|------|----------|----------|
| 审计日志 | `tests/test_audit.py` | 日志记录、查询、导出 |
| 输出解析 | `tests/test_output_parser.py` | JSON/YAML解析、Schema验证 |
| 错误处理 | `tests/test_error_handler.py` | 重试、熔断、降级 |
| 事件总线 | `tests/test_event_bus.py` | 发布、订阅、历史 |

### 7.2 集成测试

```python
# tests/test_multi_agent_integration.py

def test_audit_logging():
    """测试审计日志记录"""
    orchestrator = MultiAgentOrchestrator()
    result = orchestrator.process_message("写一个hello world程序")
    
    # 检查审计日志
    state_manager = orchestrator._get_state_manager()
    logs = state_manager.get_audit_logs(task_id=orchestrator._current_task_id)
    
    assert len(logs) > 0
    assert any(log['agent_id'] == 'taizi' for log in logs)

def test_retry_on_failure():
    """测试失败重试"""
    handler = ErrorHandler(
        retry_policy=RetryPolicy(max_attempts=3),
    )
    
    call_count = 0
    def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("timeout")
        return "success"
    
    result = handler.execute_with_retry(failing_func)
    assert result == "success"
    assert call_count == 3

def test_circuit_breaker():
    """测试熔断器"""
    cb = CircuitBreaker(failure_threshold=2)
    
    assert cb.can_execute()  # CLOSED
    
    cb.record_failure()
    assert cb.can_execute()  # Still CLOSED
    
    cb.record_failure()
    assert not cb.can_execute()  # OPEN

def test_event_bus():
    """测试事件总线"""
    bus = InMemoryEventBus()
    
    received = []
    def handler(event):
        received.append(event)
    
    bus.subscribe(EventType.TASK_CREATED, handler)
    bus.publish(Event(
        event_id="test-1",
        event_type=EventType.TASK_CREATED,
        task_id="task-1",
    ))
    
    assert len(received) == 1
    assert received[0].task_id == "task-1"
```

---

## 八、实施时间表

| 周次 | 任务 | 产出 |
|------|------|------|
| W1 | P2-3 审计日志 | 审计表、日志API |
| W1 | P2-4 输出解析 | Pydantic模型、解析器 |
| W2 | P2-2 错误处理 | 重试策略、熔断器 |
| W2 | P2-1 事件总线 | EventBus实现 |
| W3 | 测试与文档 | 单元测试、集成测试 |

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Pydantic版本兼容 | 中 | 锁定版本，添加兼容层 |
| 熔断器误触发 | 中 | 配置合理阈值，支持手动重置 |
| 事件总线内存泄漏 | 低 | 限制历史大小，定期清理 |
| 审计日志膨胀 | 中 | 添加清理策略，支持归档 |

---

## 十、后续扩展

完成P2后，可继续实施P3功能：

1. **P3-1 Dashboard API** (4h) - 基于事件总线实现
2. **P3-2 WebSocket推送** (3h) - 实时进度推送
3. **P3-3 Web Dashboard** (8h) - 可视化界面

---

**文档完成时间**: 2026-04-16
**预计开始时间**: 待定
**预计完成时间**: 开始后2周
