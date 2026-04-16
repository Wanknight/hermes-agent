---

## 四、技术方案选型

### 4.1 状态存储方案对比

| 方案 | 描述 | 优点 | 缺点 | 适用场景 | 推荐度 |
|------|------|------|------|----------|--------|
| **SQLite** | 轻量级嵌入式数据库 | • 零配置，Python 内置<br>• 文件存储，易备份<br>• 已有 SessionDB 基础<br>• 支持全文搜索(FTS5) | • 单机限制<br>• 写并发有限<br>• 无分布式能力 | 单机部署、个人使用、开发测试 | ⭐⭐⭐⭐⭐ 默认 |
| **Redis** | 内存键值数据库 | • 高性能读写<br>• 原生支持发布订阅<br>• 支持事件流<br>• 分布式友好 | • 需要额外安装<br>• 内存成本<br>• 数据持久化需配置 | 高并发、实时推送、多实例部署 | ⭐⭐⭐⭐ 可选 |
| **PostgreSQL** | 企业级关系数据库 | • JSONB 强大<br>• 事务支持完善<br>• 企业级稳定性<br>• 可扩展性强 | • 重型依赖<br>• 运维成本高<br>• 配置复杂 | 生产环境、大规模部署 | ⭐⭐⭐ 进阶 |

**推荐方案：SQLite 为默认，Redis 为可选增强**

```
状态存储架构：
┌────────────────────────────────────────────┐
│            StateManager                     │
├────────────────────────────────────────────┤
│                                             │
│   ┌─────────────┐      ┌─────────────┐    │
│   │ SQLiteStore │      │ RedisStore  │    │
│   │  (默认)     │      │   (可选)    │    │
│   └─────────────┘      └─────────────┘    │
│         │                    │            │
│         └────────┬───────────┘            │
│                  ▼                        │
│   ┌─────────────────────────────┐         │
│   │     统一抽象接口             │         │
│   │  - save_task()              │         │
│   │  - get_task()               │         │
│   │  - update_status()          │         │
│   │  - list_tasks()             │         │
│   │  - add_event()              │         │
│   │  - get_events()             │         │
│   └─────────────────────────────┘         │
└────────────────────────────────────────────┘
```

---

### 4.2 事件总线方案对比

| 方案 | 描述 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| **内存队列** | Python asyncio.Queue | • 零依赖<br>• 实现简单<br>• 低延迟 | • 进程内限制<br>• 重启丢失<br>• 无持久化 | 单进程、开发测试 |
| **Redis Streams** | Redis 流数据结构 | • 持久化<br>• 支持消费者组<br>• 消息回溯<br>• 分布式 | • 需要 Redis | 多进程、生产环境 |
| **Kafka** | 分布式消息系统 | • 高吞吐<br>• 持久化<br>• 分布式 | • 重型依赖<br>• 复杂度高 | 大规模、企业级 |

**推荐方案：内存队列为默认，Redis Streams 为可选**

```
事件总线架构：
┌────────────────────────────────────────────┐
│              EventBus                       │
├────────────────────────────────────────────┤
│                                             │
│   ┌─────────────┐      ┌─────────────┐    │
│   │ MemoryBus   │      │ RedisBus    │    │
│   │  (默认)     │      │   (可选)    │    │
│   └─────────────┘      └─────────────┘    │
│         │                    │            │
│         └────────┬───────────┘            │
│                  ▼                        │
│   ┌─────────────────────────────┐         │
│   │      统一事件接口           │         │
│   │  - publish(topic, event)    │         │
│   │  - subscribe(topic, handler)│         │
│   │  - unsubscribe(topic)       │         │
│   └─────────────────────────────┘         │
│                                             │
│   支持的事件类型：                          │
│   • task.created       任务创建            │
│   • task.assigned      任务分配            │
│   • agent.started      Agent开始          │
│   • agent.progress     进度更新           │
│   • agent.completed    Agent完成          │
│   • task.review        进入审议           │
│   • task.approved      审议通过           │
│   • task.rejected      审议封驳           │
│   • task.finalized     任务完成           │
│   • system.error       系统错误           │
└────────────────────────────────────────────┘
```

---

### 4.3 Agent 调用方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐 |
|------|------|------|------|------|
| **复用 delegate_tool** | 使用现有子代理工具 | • 已有实现<br>• 隔离执行<br>• 支持工具集控制 | • 需要适配 | ⭐⭐⭐⭐⭐ |
| **新建 multi_agent_call** | 专用 Agent 调用工具 | • 可定制化<br>• 更精细控制 | • 重复造轮子 | ⭐⭐⭐ |
| **直接 LLM 调用** | 绕过工具直接调用模型 | • 简单直接 | • 无隔离<br>• 无工具支持 | ⭐⭐ |

**推荐方案：复用并扩展现有 delegate_tool**

---

### 4.4 Dashboard 方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐 |
|------|------|------|------|------|
| **FastAPI + WebSocket** | 独立 Web 服务 | • 实时推送<br>• 标准 API | • 需要独立服务 | ⭐⭐⭐⭐ |
| **集成到 Gateway** | 在现有 Gateway 中添加 | • 无需额外服务<br>• 统一管理 | • 增加 Gateway 复杂度 | ⭐⭐⭐ |
| **CLI Dashboard** | 终端界面（Rich/TUI） | • 无需浏览器<br>• 开发者友好 | • 功能有限 | ⭐⭐⭐⭐ 辅助 |

**推荐方案：Phase 1-3 先实现 CLI Dashboard，Phase 4 可选 FastAPI Dashboard**

---

### 4.5 数据库表结构设计

```sql
-- 任务表
CREATE TABLE IF NOT EXISTS ma_tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT,  -- created, planning, reviewing, executing, completed, failed
    current_agent TEXT,
    creator TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSON  -- 任务元数据
);

-- Agent 执行记录表
CREATE TABLE IF NOT EXISTS ma_agent_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT,
    agent_id TEXT,
    input TEXT,
    output TEXT,
    status TEXT,  -- pending, running, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    tokens_used INTEGER,
    metadata JSON,
    FOREIGN KEY (task_id) REFERENCES ma_tasks(task_id)
);

-- 事件日志表
CREATE TABLE IF NOT EXISTS ma_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT,
    event_type TEXT,
    agent_id TEXT,
    payload JSON,
    created_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES ma_tasks(task_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tasks_status ON ma_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON ma_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_runs_task ON ma_agent_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_events_task ON ma_events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON ma_events(event_type);
```

---

## 五、阶段任务规划

### 5.1 Phase 1：基础框架（预计 2-3 天）

#### 任务 1.1：配置结构扩展（2小时）

**目标**：在 Hermes 配置系统中添加 multi_agent 配置块

**修改文件**：
- `hermes_cli/config.py`

**具体工作**：
1. 在 `DEFAULT_CONFIG` 中添加 `multi_agent` 配置块
2. 添加配置版本迁移逻辑（_config_version +1）
3. 添加配置验证函数

**验证标准**：
- [ ] 配置文件可以正常加载
- [ ] 配置项有默认值
- [ ] 旧配置文件可以自动迁移

---

#### 任务 1.2：模式切换命令（3小时）

**目标**：添加 `/mode` 命令，支持在会话中切换模式

**修改文件**：
- `hermes_cli/commands.py` - 添加命令定义
- `cli.py` - 添加命令处理逻辑

**新增命令**：
```python
CommandDef("mode", "切换 Agent 运行模式", "Configuration",
           aliases=("m",), args_hint="[default|three_provinces|status]"),
```

**命令实现**：
- `/mode` - 显示当前模式
- `/mode default` - 切换到默认单Agent模式
- `/mode three_provinces` - 切换到三省六部模式
- `/mode status` - 显示详细状态信息

**验证标准**：
- [ ] `/mode` 显示当前模式
- [ ] `/mode default` 切换到默认模式
- [ ] `/mode three_provinces` 切换到三省六部模式
- [ ] 配置持久化保存

---

#### 任务 1.3：Agent 角色加载器（4小时）

**目标**：实现 Agent 角色定义文件的加载和解析

**新建文件**：
- `multi_agent/__init__.py`
- `multi_agent/agent_loader.py`

**核心类**：
- `AgentRole` - Agent 角色数据类
- `AgentLoader` - 角色加载器

**功能**：
1. 支持从 YAML 文件加载角色定义
2. 支持从用户目录加载自定义定义（`~/.hermes/agents/`）
3. 支持内置默认定义（`multi_agent/agents/`）
4. 缓存已加载的角色

**验证标准**：
- [ ] 可以加载 YAML 格式的 Agent 定义
- [ ] 支持从用户目录加载自定义定义
- [ ] 支持内置默认定义
- [ ] 加载结果正确解析为 AgentRole 对象

---

#### 任务 1.4：基础调度器框架（6小时）

**目标**：实现 MultiAgentOrchestrator 的核心框架

**新建文件**：
- `multi_agent/orchestrator.py`
- `multi_agent/agent_pool.py`

**核心类**：
- `TaskContext` - 任务上下文数据类
- `MultiAgentOrchestrator` - 多Agent调度器
- `AgentPool` - Agent角色池管理

**核心功能**：
1. 检查多Agent模式是否启用
2. 创建和管理任务
3. 根据模式路由消息
4. 调用 Agent 执行任务

**验证标准**：
- [ ] 调度器可以初始化
- [ ] 可以创建任务
- [ ] 可以调用 Agent 执行
- [ ] 任务状态正确流转

---

### 5.2 Phase 2：核心流程（预计 3-4 天）

#### 任务 2.1：消息分类器实现（4小时）

**目标**：实现太子的消息分类逻辑

**新建文件**：
- `multi_agent/classifier.py`

**核心类**：
- `ClassificationResult` - 分类结果数据类
- `MessageClassifier` - 消息分类器

**分类逻辑**：
1. 规则优先：关键词快速匹配
2. LLM 辅助：模糊情况调用 LLM 判断
3. 置信度评估

**验证标准**：
- [ ] 问候语正确识别为闲聊
- [ ] 明确任务指令识别为旨意
- [ ] 边界情况正确处理
- [ ] LLM 辅助分类正常工作

---

#### 任务 2.2：工作流引擎（8小时）

**目标**：实现完整的三省六部工作流引擎

**新建文件**：
- `multi_agent/workflow.py`

**核心类**：
- `WorkflowState` - 工作流状态枚举
- `WorkflowContext` - 工作流上下文
- `ThreeProvincesWorkflow` - 三省六部工作流引擎

**工作流步骤**：
1. 分类（太子）
2. 规划（中书省）
3. 审议循环（门下省）
4. 执行（尚书省 + 六部）
5. 汇总报告

**审议循环**：
- 最多3轮审议
- 封驳后可修改重试
- 第3轮强制通过

**验证标准**：
- [ ] 完整流程可以执行
- [ ] 审议循环正确处理
- [ ] 封驳后可以修改重试
- [ ] 第N轮强制通过正常
- [ ] 历史记录完整

---

#### 任务 2.3：Agent 间调用适配（4小时）

**目标**：复用 delegate_tool 实现 Agent 间调用

**修改文件**：
- `tools/delegate_tool.py` - 扩展支持 multi-agent 模式
- `multi_agent/agent_pool.py` - 调用 delegate_tool

**核心功能**：
1. 解析需要调用的下游 Agent
2. 检查调用权限
3. 通过 delegate_tool 调用
4. 返回结果聚合

**验证标准**：
- [ ] 中书省可以调用门下省
- [ ] 中书省可以调用尚书省
- [ ] 尚书省可以调用六部
- [ ] 调用权限正确检查
- [ ] 结果正确返回

---

#### 任务 2.4：状态持久化（4小时）

**目标**：实现 SQLite 状态存储

**新建文件**：
- `multi_agent/state_manager.py`

**核心类**：
- `MultiAgentStateManager` - 状态管理器

**核心功能**：
1. 任务创建和查询
2. 状态更新
3. Agent 执行记录
4. 事件日志
5. 历史回溯

**验证标准**：
- [ ] 任务可以创建和读取
- [ ] 状态可以更新
- [ ] 事件日志可以添加
- [ ] 历史可以回溯
- [ ] 数据库文件正确创建

---

### 5.3 Phase 3：完善功能（预计 2-3 天）

#### 任务 3.1：事件总线（内存版）（4小时）

**新建文件**：
- `multi_agent/event_bus.py`

**核心类**：
- `Event` - 事件数据类
- `MemoryEventBus` - 内存事件总线

**核心功能**：
1. 主题订阅/取消订阅
2. 事件发布
3. 异步事件分发
4. 通配符匹配

**验证标准**：
- [ ] 可以订阅主题
- [ ] 可以发布事件
- [ ] 事件正确分发
- [ ] 异步处理正常

---

#### 任务 3.2：审议封驳逻辑完善（4小时）

**目标**：完善门下省审议逻辑

**修改文件**：
- `multi_agent/agents/menxia.yaml` - 更新 prompt
- `multi_agent/workflow.py` - 完善审议循环

**审议维度**：
1. 可行性（0-10分）
2. 完整性（0-10分）
3. 风险管理（0-10分）
4. 资源配置（0-10分）

**输出格式**：
- 准奏/封驳结论
- 评分明细
- 问题列表
- 修改建议

**验证标准**：
- [ ] 四维度审议正常执行
- [ ] 评分系统正确计算
- [ ] 封驳理由清晰
- [ ] 修改建议具体

---

#### 任务 3.3：错误处理与重试（4小时）

**目标**：完善的错误处理和重试机制

**新建文件**：
- `multi_agent/error_handler.py`

**核心类**：
- `ErrorType` - 错误类型枚举
- `ErrorContext` - 错误上下文
- `MultiAgentErrorHandler` - 错误处理器
- `MultiAgentError` - 自定义异常

**错误类型**：
- LLM_ERROR - LLM 调用错误
- AGENT_ERROR - Agent 执行错误
- TIMEOUT_ERROR - 超时错误
- VALIDATION_ERROR - 验证错误
- SYSTEM_ERROR - 系统错误

**重试策略**：
- 最多3次重试
- 指数退避延迟
- 错误日志记录

**验证标准**：
- [ ] 错误正确分类
- [ ] 重试机制正常
- [ ] 错误日志完整
- [ ] 超时正确处理

---

#### 任务 3.4：日志与审计（2小时）

**目标**：完善的日志记录和审计追踪

**新建文件**：
- `multi_agent/audit.py`

**核心类**：
- `MultiAgentAudit` - 审计日志管理

**核心功能**：
1. 任务事件记录
2. Agent 调用记录
3. 审议结果记录
4. 审计追踪查询
5. 审计报告生成

**验证标准**：
- [ ] 事件日志正确写入
- [ ] 审计追踪可回溯
- [ ] 报告生成正常
- [ ] 文件存储正确

---

### 5.4 Phase 4：可选增强（预计 2-3 天）

#### 任务 4.1：Dashboard API（8小时）

**目标**：提供 REST API 用于外部监控

**新建文件**：
- `multi_agent/dashboard/__init__.py`
- `multi_agent/dashboard/api.py`

**API 端点**：
- `GET /` - 服务状态
- `GET /tasks` - 任务列表
- `GET /tasks/{task_id}` - 任务详情
- `GET /tasks/{task_id}/events` - 任务事件
- `GET /tasks/{task_id}/audit` - 审计报告

**验证标准**：
- [ ] API 正常响应
- [ ] 任务列表正确
- [ ] 任务详情正确
- [ ] 审计报告完整

---

#### 任务 4.2：WebSocket 实时推送（6小时）

**目标**：实时推送 Agent 执行进度

**新建文件**：
- `multi_agent/dashboard/websocket_handler.py`

**核心功能**：
1. WebSocket 连接管理
2. 任务进度推送
3. 思考过程推送
4. 状态变更通知

**推送事件类型**：
- `progress` - 进度更新
- `thought` - 思考过程
- `status_change` - 状态变更
- `agent_call` - Agent 调用

**验证标准**：
- [ ] WebSocket 连接稳定
- [ ] 进度推送及时
- [ ] 思考过程可见
- [ ] 状态变更通知

---

#### 任务 4.3：Redis 事件总线（可选）（4小时）

**目标**：支持 Redis 作为事件总线后端

**修改文件**：
- `multi_agent/event_bus.py` - 添加 RedisBackend

**核心功能**：
1. Redis Pub/Sub 集成
2. 事件持久化
3. 消费者组支持

**验证标准**：
- [ ] Redis 连接正常
- [ ] 发布订阅正常
- [ ] 事件传递正确
- [ ] 错误处理完善
