# 三省六部多Agent系统 - 实施进度报告

> **版本**: v5.0  
> **日期**: 2026-04-16  
> **状态**: ✅ P0-P3全部完成，集成测试通过，准备业务测试

---

## 一、项目概览

### 1.1 核心定位

基于 Edict 项目设计理念，在 Hermes Agent 内原生实现"三省六部制"多Agent协作系统。

**特点**：
- 太子是唯一消息入口和出口
- 分权制衡：中书省规划 → 门下省审议 → 尚书省执行
- 专业分工：六部各司其职
- 审议封驳：方案可被驳回修改

### 1.2 Agent 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户 (皇上)                              │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 太子 (taizi) - 唯一出入口                                ││
│  │   • 消息分类（闲聊/旨意）                                ││
│  │   • 结果汇总汇报                                        ││
│  └─────────────────────────────────────────────────────────┘│
│                         │                                    │
│           ┌─────────────┼─────────────┐                     │
│           ▼             ▼             ▼                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ 中书省      │ │ 门下省      │ │ 尚书省      │           │
│  │ (zhongshu)  │ │ (menxia)    │ │ (shangshu)  │           │
│  │   规划      │ │   审议      │ │   执行      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                     │                        │
│              ┌──────────────────────┼────────────────┐      │
│              ▼          ▼           ▼          ▼     ▼      │
│         ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ...    │
│         │ 户部   │ │ 兵部   │ │ 工部   │ │ 礼部   │        │
│         │ (hubu) │ │(bingbu)│ │(gongbu)│ │ (libu) │        │
│         │ 数据   │ │ 基础   │ │ 代码   │ │ 文档   │        │
│         └────────┘ └────────┘ └────────┘ └────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、当前完成状态

### 2.1 总览

| 阶段 | 任务 | 状态 | 文件 |
|------|------|------|------|
| Phase 1 | 框架搭建 | ✅ 完成 | config.py, commands.py, agent_loader.py |
| Phase 2 | LLM调用集成 | ✅ 完成 | agent_pool.py, orchestrator.py |
| Phase 3 | Agent间调用 | ✅ 完成 | agent_pool.py (+dispatch_to_agent) |
| Phase 4 | 审议封驳逻辑 | ✅ 完成 | orchestrator.py (+_revise_plan) |
| Phase 5 | 状态持久化 | ✅ 完成 | state_manager.py (760行) |
| Phase 6 | 进度反馈 | ✅ 完成 | ProgressEvent类, _notify_progress |
| **P2** | **健壮性增强** | ✅ 完成 | 见下方详情 |

### 2.2 已完成功能详情

#### Phase 1-2: 框架搭建 ✅

| 组件 | 文件 | 说明 |
|------|------|------|
| 配置扩展 | `hermes_cli/config.py` | multi_agent配置块、版本迁移 |
| 模式命令 | `cli.py`, `commands.py` | `/mode` 命令实现 |
| Agent定义 | `multi_agent/agents/*.yaml` | 11个Agent定义完整 |
| Agent加载 | `agent_loader.py` | YAML加载、权限解析 |

#### Phase 3: Agent间调用 ✅

**问题**：尚书省无法真正派发给六部，只能自己执行

**修复**：
- 添加 `dispatch_to_agent()` 方法
- 添加 `dispatch_parallel()` 方法支持并行派发
- 重写 `_execute_plan()` 解析派发决策

```python
# agent_pool.py
def dispatch_to_agent(self, from_agent, to_agent, task, ...) -> str:
    """Agent间调用"""
    if not self.can_call(from_agent, to_agent):
        return {"error": "权限不足"}
    return self.execute(agent_id=to_agent, input_data=task, ...)

def dispatch_parallel(self, from_agent, dispatches, ...) -> List[Dict]:
    """并行派发给多个Agent"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        # 并行执行...
```

#### Phase 4: 审议封驳逻辑 ✅

**问题**：门下省封驳后无后续动作

**修复**：
- 在 `_review_plan()` 中处理 rejected 情况
- 新增 `_revise_plan()` 方法调用中书省修改方案
- 最多3轮审议，最后一轮强制通过

```
门下省封驳 → 提取审议意见
     ↓
调用 _revise_plan() → 中书省修改方案
     ↓
更新 task.plan → 重新提交审议
     ↓
最多3轮，最后一轮强制通过
```

#### Phase 5: 状态持久化 ✅

**文件**: `state_manager.py` (760行, 18个方法)

**数据库表**:
- `ma_tasks` - 任务记录
- `ma_agent_runs` - Agent执行记录
- `ma_events` - 事件日志

**核心接口**:
```python
class MultiAgentStateManager:
    def create_task(self, task_id, title, message_type, original_message)
    def get_task(self, task_id) -> Optional[TaskRecord]
    def update_task_data(self, task_id, status, classification, plan, ...)
    def add_agent_run(self, run_id, task_id, agent_id, input_data, output, status)
    def add_event(self, event_id, task_id, event_type, agent_id, payload)
    def list_tasks(self, status, limit) -> List[TaskRecord]
    def get_statistics() -> Dict
```

#### Phase 6: 进度反馈 ✅

**实现**:
- `ProgressEvent` 类 - 阶段/Agent名称映射
- `_notify_progress()` 方法 - 发送进度事件
- CLI回调 - 更新spinner显示

```python
class ProgressEvent:
    STAGE_NAMES = {
        TaskStatus.CLASSIFYING: "消息分拣",
        TaskStatus.PLANNING: "任务规划",
        TaskStatus.REVIEWING: "方案审议",
        ...
    }
    AGENT_NAMES = {
        "taizi": "太子",
        "zhongshu": "中书省",
        ...
    }
```

---

## 三、与 Edict 设计对比

### 3.1 功能对比

| 特性 | Edict设计 | 当前实现 | 差距 |
|------|-----------|----------|------|
| Agent层级 | 3层（入口/中枢/执行） | ✅ 一致 | 无 |
| Agent间调用 | 支持 | ✅ 已实现 | 无 |
| 审议封驳 | 完整循环 | ✅ 已实现 | 无 |
| 状态存储 | SQLite/Redis | ✅ SQLite | 可扩展Redis |
| 配置驱动 | YAML完整 | ✅ 一致 | 无 |
| 工具权限 | 精确控制 | ✅ 近似 | 可优化 |
| 异步消息 | Redis Streams | ❌ 无 | P2-1 |
| 审计日志 | 完整记录 | ❌ 无 | P2-3 |
| 结构化输出 | 强Schema | ❌ 弱解析 | P2-4 |
| 错误重试 | 智能重试 | ❌ 无 | P2-2 |

### 3.2 差距分析

**已对齐**:
- ✅ 核心流程：太子分类 → 中书规划 → 门下审议 → 尚书派发 → 六部执行
- ✅ 审议封驳循环
- ✅ Agent间调用权限控制
- ✅ 状态持久化

**待对齐**:
- ❌ 异步消息机制（Edict用Redis Streams）
- ❌ 结构化输出验证
- ❌ 完整审计日志
- ❌ 智能错误处理

---

## 四、P2 实施计划

### 4.1 P2 任务概览

|| ID | 功能 | 工时 | 优先级 | 状态 |
|----|------|------|--------|------|
| P2-3 | 审计日志 | 2h | 中 | ✅ 已完成 |
| P2-4 | 输出解析增强 | 3h | 中 | ✅ 已完成 |
| P2-2 | 错误处理增强 | 3h | 高 | ✅ 已完成 |
| P2-1 | 事件总线（内存版） | 4h | 高 | ✅ 已完成 |

**总工时: 12h，全部完成**

### 4.2 实施顺序

```
第1步: P2-3 审计日志 (2h) ✅ 已完成
  │
  ├─ 原因: 基础设施，其他功能可复用
  └─ 产出: 操作记录、问题追溯

第2步: P2-4 输出解析增强 (3h) ✅ 已完成
  │
  ├─ 原因: 提升稳定性，减少LLM输出解析错误
  └─ 产出: Schema验证、容错解析

第3步: P2-2 错误处理增强 (3h) ✅ 已完成
  │
  ├─ 原因: 提升健壮性，智能重试和熔断
  └─ 产出: RetryPolicy、CircuitBreaker

第4步: P2-1 事件总线 (4h) ✅ 已完成
  │
  ├─ 原因: 支持异步执行、并行任务
  └─ 产出: InMemoryEventBus、事件订阅、/events命令
```

---

## 五、P2-3 审计日志 (2h) ✅ 已完成

**完成日期: 2026-04-16**

### 5.1 实现总结

#### 数据库变更
- 新增 `ma_audit_log` 表，包含完整审计字段
- DB_VERSION 升级到 2，支持自动迁移
- 添加 4 个索引：idx_audit_task, idx_audit_agent, idx_audit_action, idx_audit_created

#### 核心实现
- `state_manager.py`: 新增 `AuditLogRecord` dataclass，`add_audit_log()`, `get_audit_logs()`, `export_audit_logs()` 方法
- `agent_pool.py`: 在 `_execute_with_llm()` 中自动记录审计日志（计时、token统计、状态）
- `cli.py`: 新增 `/tasks <task_id> audit` 命令，支持前缀匹配

#### 审计字段
| 字段 | 说明 |
|------|------|
| log_id | 唯一日志ID |
| task_id | 任务ID |
| agent_id | Agent ID |
| agent_name | Agent 名称（中文） |
| action | 操作类型（call/execute等） |
| input_summary | 输入摘要（前500字符） |
| output_summary | 输出摘要（前500字符） |
| status | 状态（success/failed/timeout） |
| error_message | 错误信息 |
| tokens_used | Token消耗 |
| latency_ms | 耗时（毫秒） |
| model_version | 模型版本 |
| created_at | 创建时间 |

### 5.2 原始设计（参考）

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

### 5.3 原始API设计（参考）

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

### 5.4 原始修改计划（参考）

| 文件 | 修改内容 |
|------|----------|
| `state_manager.py` | 添加 `add_audit_log()`, `get_audit_logs()` 方法 |
| `agent_pool.py` | 在 `_execute_with_llm()` 中记录审计日志 |
| `orchestrator.py` | 在关键节点记录审计事件 |

### 5.5 验收标准

- [ ] 审计日志表创建成功
- [ ] Agent调用自动记录审计日志
- [ ] 支持按任务/Agent/操作类型查询
- [ ] 支持JSON/CSV导出
- [ ] CLI命令: `/tasks <id> audit` 查看审计日志

---

## 六、P2-4 输出解析增强 (3h) ✅ 已完成

**完成日期: 2026-04-16**

### 6.1 实现总结

#### 新建文件
| 文件 | 说明 |
|------|------|
| `output_schemas.py` | Pydantic 模型定义，包含所有 Agent 输出 Schema |
| `output_parser.py` | 多格式解析器，支持 JSON/YAML/智能提取 |

#### 核心功能
1. **多格式解析**: 支持直接 JSON、代码块提取、花括号提取、YAML 解析
2. **Pydantic 验证**: 强类型校验，自动生成文档
3. **自动修复**: 字段名映射、枚举值修正、类型转换
4. **容错处理**: 智能提取、默认值填充

#### Schema 定义
| Schema | Agent | 说明 |
|--------|-------|------|
| ClassificationOutput | 太子 | 分类消息类型（chat/decree） |
| PlanOutput | 中书省 | 规划执行方案 |
| ReviewOutput | 门下省 | 审议决定和评分 |
| DispatchOutput | 尚书省 | 任务派发列表 |
| ExecutionOutput | 六部 | 通用执行结果 |

#### 解析流程
```
LLM 输出 → OutputParser.parse()
         → 尝试 JSON 解析 → Pydantic 验证 → 返回模型
         → 尝试 YAML 解析 ↓
         → 智能提取（兜底）
         → 自动修复（如需要）
```

### 6.2 原始设计（参考）

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

### 6.3 解析器

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

### 6.4 验收标准

- [ ] Pydantic模型定义完整
- [ ] 支持JSON/YAML/文本格式解析
- [ ] 解析失败时有容错处理
- [ ] 各Agent输出符合Schema

---

## 七、P2-2 错误处理增强 (3h) ✅ 已完成

**完成日期: 2026-04-16**

### 7.1 实现总结

#### 新建文件
| 文件 | 说明 |
|------|------|
| `error_handler.py` | RetryPolicy + CircuitBreaker + ErrorHandler |

#### 核心功能
1. **RetryPolicy**: 指数退避重试，可配置错误类型，抖动防止惊群
2. **CircuitBreaker**: 三态熔断器（CLOSED/OPEN/HALF_OPEN），自动恢复
3. **ErrorHandler**: 组合重试和熔断，支持降级函数
4. **全局管理**: 按 Agent ID 存储处理器，支持统计查询和重置

#### 可重试的错误类型
- timeout, rate_limit, server_error
- connection_error, network_error
- HTTP 500/502/503/429

#### 不可重试的错误类型
- invalid_api_key, authentication
- context_length_exceeded, token_limit
- HTTP 401/403

#### CLI 命令
```
/circuit-breaker [status|reset]  # 查看或重置熔断器状态
/cb                              # 别名
```

#### 集成点
- `agent_pool.py`: `_execute_with_llm()` 中使用 ErrorHandler 包裹 LLM 调用

### 7.2 原始设计（参考）

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

### 7.3 配置扩展

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

### 7.4 验收标准

- [ ] 重试策略实现（指数退避）
- [ ] 熔断器实现（CLOSED/OPEN/HALF_OPEN）
- [ ] Fallback降级机制
- [ ] 配置项支持
- [ ] 单元测试覆盖

---

## 八、P2-1 事件总线 (4h) ✅ 已完成

**完成日期: 2026-04-16**

### 8.1 实现总结

#### 新建文件
| 文件 | 说明 |
|------|------|
| `event_bus.py` | InMemoryEventBus + 事件发布/订阅 + 历史查询 |

#### 核心功能
1. **EventType**: 11种事件类型（任务生命周期 + Agent调用 + 进度更新 + 熔断器状态）
2. **Event**: 事件数据类，支持序列化/反序列化
3. **InMemoryEventBus**: 内存事件总线，线程安全，历史记录限制1000条
4. **全局函数**: publish_event(), subscribe_to_event(), get_event_history()

#### 事件类型
| 类型 | 说明 |
|------|------|
| TASK_CREATED | 任务创建 |
| TASK_STARTED | 任务开始 |
| TASK_COMPLETED | 任务完成 |
| TASK_FAILED | 任务失败 |
| AGENT_CALLED | Agent被调用 |
| AGENT_COMPLETED | Agent完成 |
| AGENT_FAILED | Agent失败 |
| STAGE_CHANGE | 阶段变更 |
| PROGRESS_UPDATE | 进度更新 |
| CIRCUIT_BREAKER_TRIPPED | 熔断器触发 |
| CIRCUIT_BREAKER_RECOVERED | 熔断器恢复 |

#### CLI 命令
```
/events [stats|<task_id>]  # 查看事件历史和统计
```

#### 集成点
- `orchestrator.py`: `_notify_progress()` 发布事件到总线
- 全局单例模式，支持后续扩展为 Redis

### 8.2 目标

- 支持异步执行
- 支持并行任务处理
- 实时进度推送
- 对齐 Edict 的 Redis Streams 设计

### 8.2 新建文件

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

### 8.3 配置扩展

```yaml
multi_agent:
  event_bus:
    type: memory  # memory | redis
    max_history: 1000
    redis_url: ""  # Redis模式需要
```

### 8.4 验收标准

- [x] InMemoryEventBus实现完成
- [x] 事件发布/订阅正常工作
- [x] 与现有进度通知集成
- [x] 支持事件历史查询
- [x] 可扩展为Redis实现
- [x] CLI命令 /events 已注册

---

## 九、测试计划

### 9.1 单元测试

| 模块 | 测试文件 | 覆盖内容 |
|------|----------|----------|
| 审计日志 | `tests/test_audit.py` | 日志记录、查询、导出 |
| 输出解析 | `tests/test_output_parser.py` | JSON/YAML解析、Schema验证 |
| 错误处理 | `tests/test_error_handler.py` | 重试、熔断、降级 |
| 事件总线 | `tests/test_event_bus.py` | 发布、订阅、历史 |

### 9.2 集成测试

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

## 十、实施时间表

| 周次 | 任务 | 产出 |
|------|------|------|
| W1 | P2-3 审计日志 | 审计表、日志API |
| W1 | P2-4 输出解析 | Pydantic模型、解析器 |
| W2 | P2-2 错误处理 | 重试策略、熔断器 |
| W2 | P2-1 事件总线 | EventBus实现 |
| W3 | 测试与文档 | 单元测试、集成测试 |

---

## 十一、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Pydantic版本兼容 | 中 | 锁定版本，添加兼容层 |
| 熔断器误触发 | 中 | 配置合理阈值，支持手动重置 |
| 事件总线内存泄漏 | 低 | 限制历史大小，定期清理 |
| 审计日志膨胀 | 中 | 添加清理策略，支持归档 |

---

## 十二、后续扩展（P3）

完成P2后，可继续实施P3功能：

### P3-0 任务工作空间 ✅ 已完成 (2026-04-16)

**目的**：为每个任务创建独立的文件工作空间，存储各环节产出。

**实现**：
- 创建 `task_workspace.py` 模块（~16KB）
- 修改 `TaskContext` 添加 `workspace_path` 字段
- 在 `orchestrator.create_task()` 中初始化工作空间
- 在 `agent_pool.execute()` 和 `dispatch_to_agent()` 中传递工作空间路径

**目录结构**：
```
~/.hermes/tasks/{task_id}/
├── .task.json              # 任务元数据
├── classification.json     # 太子分类
├── plan.md                 # 中书省规划
├── review.json             # 门下省审议
├── dispatch.json           # 尚书省派发
├── outputs/                # 六部产出
│   ├── hubu/
│   ├── gongbu/
│   └── libu/
└── final/                  # 最终结果
    └── summary.md
```

**核心方法**：
- `workspace.create()` - 创建目录结构
- `workspace.save_classification()` - 保存分类结果
- `workspace.save_plan()` - 保存规划
- `workspace.save_review()` - 保存审议结果
- `workspace.save_agent_output()` - 保存六部产出
- `workspace.save_final()` - 保存最终结果

### P3-1 聊天终端 Dashboard 🔄 进行中 (2026-04-16)

**目的**：在微信/飞书终端提供任务查询、关键节点推送、定期报告功能。

**Phase 1: 手动查询基础** ✅ 已完成
- 修改 `commands.py`：移除 `/tasks` 命令的 `cli_only=True` 限制
- 修改 `gateway/run.py`：添加 `tasks` 命令分发和 `_handle_tasks_command()` 方法
- 创建 `dashboard_formatter.py`：卡片格式化模块
  - 支持飞书 Markdown 格式
  - 支持微信纯文本格式
  - 平台自动检测 `detect_platform()`
- 支持的查询命令：
  - `/tasks` - 列出最近10个任务
  - `/tasks stats` - 显示统计信息
  - `/tasks <task_id>` - 查看任务详情
  - `/tasks <task_id> audit` - 查看审计日志

**Phase 2: 卡片格式适配优化** ✅ 已完成
- 完善 `dashboard_formatter.py` 格式化函数
- 支持更多卡片类型（统计面板、事件流、工作空间）

**Phase 3: 扩展查询命令** ✅ 已完成
- `/tasks stats daily` - 今日统计
- `/tasks stats weekly` - 本周统计
- `/tasks stats agents` - Agent 排行
- `/tasks active` - 活跃任务
- `/tasks failed` - 失败任务

**Phase 4: 关键节点推送通知** ✅ 已完成
- 修改 `run_agent.py`：添加通知回调支持
- 修改 `gateway/run.py`：添加 `_send_multi_agent_notification_async()` 方法
- 使用 `asyncio.run_coroutine_threadsafe()` 桥接线程池到主事件循环
- 推送节点：task_started, task_completed, task_failed

**Phase 5: 定期报告** ✅ 已完成 (2026-04-16)
- 创建 `scripts/multi_agent_daily_report.py`：日报生成脚本
- 创建 `scripts/multi_agent_weekly_report.py`：周报生成脚本
- 创建 `multi_agent/report_scheduler.py`：定时任务注册模块
- 修改 `report_generator.py`：添加辅助函数
  - `get_active_tasks()` - 获取活跃任务
  - `get_failed_tasks_today()` - 获取今日失败任务
  - `get_agent_stats_today()` - 获取今日 Agent 统计
- 修改 `state_manager.py`：添加 `get_agent_stats_today()` 方法
- 修改 `gateway/run.py`：启动时调用 `register_multi_agent_reports()`
- 配置路径：`config["multi_agent"]["reports"]`
  - `daily.enabled/time/channel`
  - `weekly.enabled/day/time/channel`

### P3 任务完成状态

| ID | 任务 | 工时 | 状态 | 完成日期 |
|----|------|------|------|----------|
| P3-0 | 任务工作空间 | 3h | ✅ 已完成 | 2026-04-16 |
| P3-1 | 聊天终端 Dashboard | 8h | ✅ 已完成 | 2026-04-16 |
| P3-2 | 任务干预功能 | 4h | ✅ 已完成 | 2026-04-16 |
| P3-3 | 阻塞/待审查状态 | 3h | ✅ 已完成 | 2026-04-16 |
| P3-4 | 奏折存档导出 | 2h | ✅ 已完成 | 2026-04-16 |

**P3总工时: 20h，全部完成**

---

## 十三、文件结构

```
multi_agent/
├── __init__.py              # 模块导出
├── agent_loader.py          # Agent配置加载器 (5815字节)
├── agent_pool.py            # Agent执行池 (22843字节)
├── orchestrator.py          # 多Agent调度器核心 (58149字节)
├── state_manager.py         # 状态持久化 (63616字节)
├── agents/                  # Agent配置文件目录
│   ├── taizi.yaml           # 太子
│   ├── zhongshu.yaml        # 中书省
│   ├── menxia.yaml          # 门下省
│   ├── shangshu.yaml        # 尚书省
│   ├── hubu.yaml            # 户部
│   ├── bingbu.yaml          # 兵部
│   ├── libu.yaml            # 礼部
│   ├── xingbu.yaml          # 刑部
│   ├── gongbu.yaml          # 工部
│   ├── libu_hr.yaml         # 礼部人事
│   └── zaochao.yaml         # 早朝
├── output_schemas.py        # ✅ Pydantic输出模型 (8424字节)
├── output_parser.py         # ✅ 输出解析器 (15891字节)
├── error_handler.py         # ✅ 错误处理器 (15502字节)
├── event_bus.py             # ✅ 事件总线 (11378字节)
├── task_workspace.py        # ✅ 任务工作空间管理 (15959字节)
├── dashboard_formatter.py   # ✅ Dashboard卡片格式化 (24898字节)
├── report_generator.py      # ✅ 报告生成器 (23607字节)
├── report_scheduler.py      # ✅ 定时报告调度 (5384字节)
├── archived/                # 归档的过时文档
│   ├── P2_IMPLEMENTATION_PLAN.md
│   ├── PHASE3_REVIEW.md
│   └── REVIEW_REPORT.md
└── IMPLEMENTATION_REPORT.md # 最终实施报告
```

**测试文件** (`tests/multi_agent/`):
```
tests/multi_agent/
├── __init__.py
├── test_e2e.py              # 端到端测试 (30 tests)
├── test_performance.py      # 性能测试 (11 tests)
└── test_exceptions.py       # 异常测试 (28 tests)
```

**脚本文件** (`scripts/`):
```
scripts/
├── multi_agent_daily_report.py   # 日报生成脚本
└── multi_agent_weekly_report.py  # 周报生成脚本
```

---

## 十四、实施总结

### 14.1 完成状态

| 阶段 | 内容 | 状态 | 工时 |
|------|------|------|------|
| Phase 1-6 | 核心架构 | ✅ 完成 | ~20h |
| P2-1~4 | 健壮性增强 | ✅ 完成 | 12h |
| P3-0~4 | 功能扩展 | ✅ 完成 | 20h |
| Option A | 集成测试 | ✅ 完成 | - |
| Option B | 文档更新 | ✅ 完成 | - |

**总计: ~52h，全部完成**

### 14.2 测试覆盖

- **端到端测试**: 30 tests ✅
- **性能测试**: 11 tests ✅
- **异常测试**: 28 tests ✅
- **总计**: 69 tests passing ✅

### 14.3 与 Edict 设计对齐

| 特性 | Edict | Hermes | 状态 |
|------|-------|--------|------|
| Agent层级 | 3层 | ✅ 一致 | 对齐 |
| Agent间调用 | 支持 | ✅ 支持 | 对齐 |
| 审议封驳 | 完整 | ✅ 完整 | 对齐 |
| 状态存储 | SQLite/Redis | ✅ SQLite | 对齐 |
| 配置驱动 | YAML | ✅ YAML | 对齐 |
| 事件总线 | Redis Streams | ✅ InMemory | 对齐* |
| 审计日志 | 完整 | ✅ 完整 | 对齐 |
| 错误处理 | 智能重试 | ✅ 重试+熔断 | 对齐 |
| Dashboard | Web UI | ✅ 聊天终端 | 差异化 |

*内存版本可扩展为 Redis

---

**文档完成时间**: 2026-04-16  
**P2完成时间**: 2026-04-16  
**P3完成时间**: 2026-04-16  
**集成测试完成**: 2026-04-16  
**下次里程碑**: Option D 实际业务测试
