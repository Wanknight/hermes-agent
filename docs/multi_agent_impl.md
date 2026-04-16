---

## 六、代码结构

### 6.1 完整目录结构

```
hermes-agent/
├── multi_agent/                          # 🆕 多Agent模块
│   ├── __init__.py                       # 模块入口
│   ├── orchestrator.py                   # 调度器核心
│   ├── agent_pool.py                     # Agent角色池管理
│   ├── agent_loader.py                   # Agent定义加载器
│   ├── workflow.py                       # 工作流引擎
│   ├── classifier.py                     # 消息分类器
│   ├── event_bus.py                      # 事件总线
│   ├── state_manager.py                  # 状态持久化
│   ├── error_handler.py                  # 错误处理
│   ├── audit.py                          # 审计日志
│   │
│   ├── agents/                           # 内置Agent定义
│   │   ├── taizi.yaml                    # 太子
│   │   ├── zhongshu.yaml                 # 中书省
│   │   ├── menxia.yaml                   # 门下省
│   │   ├── shangshu.yaml                 # 尚书省
│   │   ├── hubu.yaml                     # 户部
│   │   ├── bingbu.yaml                   # 兵部
│   │   ├── libu.yaml                     # 礼部
│   │   ├── xingbu.yaml                   # 刑部
│   │   ├── gongbu.yaml                   # 工部
│   │   ├── libu_hr.yaml                  # 吏部
│   │   └── zaochao.yaml                  # 早朝官
│   │
│   └── dashboard/                        # Dashboard (Phase 4)
│       ├── __init__.py
│       ├── api.py                        # FastAPI 接口
│       └── websocket_handler.py          # WebSocket 推送
│
├── hermes_cli/
│   ├── config.py                         # ✏️ 修改：添加 multi_agent 配置
│   └── commands.py                       # ✏️ 修改：添加 /mode 命令
│
├── cli.py                                # ✏️ 修改：模式切换处理
│
├── gateway/
│   └── run.py                            # ✏️ 修改：模式分发逻辑
│
├── tools/
│   └── delegate_tool.py                  # ✏️ 修改：支持 multi-agent 调用
│
└── tests/
    └── test_multi_agent/                 # 🆕 测试目录
        ├── test_orchestrator.py
        ├── test_workflow.py
        ├── test_state_manager.py
        ├── test_event_bus.py
        └── test_classifier.py
```

---

### 6.2 核心模块职责

| 模块 | 文件 | 职责 | 依赖 |
|------|------|------|------|
| 调度器 | `orchestrator.py` | 任务创建、流程路由、模式管理 | agent_pool, state_manager |
| 角色池 | `agent_pool.py` | Agent 角色管理、调用执行 | agent_loader, delegate_tool |
| 加载器 | `agent_loader.py` | YAML 加载、角色定义解析 | 无 |
| 工作流 | `workflow.py` | 三省六部流程控制 | agent_pool, state_manager, event_bus |
| 分类器 | `classifier.py` | 消息分类、闲聊/旨意判断 | 无 |
| 事件总线 | `event_bus.py` | 事件发布订阅 | asyncio |
| 状态管理 | `state_manager.py` | SQLite 持久化 | sqlite3 |
| 错误处理 | `error_handler.py` | 重试、错误分类 | asyncio |
| 审计 | `audit.py` | 日志记录、审计追踪 | 无 |

---

### 6.3 接口定义

#### 6.3.1 Orchestrator 接口

```python
class MultiAgentOrchestrator:
    """多Agent调度器"""
    
    def __init__(self, config: dict):
        """初始化调度器"""
        pass
    
    def is_enabled(self) -> bool:
        """检查是否启用多Agent模式"""
        pass
    
    def process_message(self, message: str, context: dict) -> str:
        """处理用户消息（多Agent模式入口）"""
        pass
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        pass
    
    def list_tasks(self, status: str = None, limit: int = 50) -> List[dict]:
        """列出任务"""
        pass
```

#### 6.3.2 AgentPool 接口

```python
class AgentPool:
    """Agent 角色池管理"""
    
    def __init__(self, config: dict, loader: AgentLoader):
        """初始化角色池"""
        pass
    
    def execute(self, agent_id: str, task_id: str, input_data: str, 
                context: dict) -> dict:
        """执行 Agent 任务"""
        pass
    
    def can_call(self, from_agent: str, to_agent: str) -> bool:
        """检查 Agent 间调用权限"""
        pass
    
    def get_prompt(self, agent_id: str) -> str:
        """获取 Agent 的 prompt"""
        pass
```

#### 6.3.3 StateManager 接口

```python
class MultiAgentStateManager:
    """多Agent状态管理器"""
    
    def create_task(self, task_id: str, title: str, creator: str, 
                    metadata: dict = None) -> dict:
        """创建任务"""
        pass
    
    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务"""
        pass
    
    def update_task_status(self, task_id: str, status: str, 
                          current_agent: str = None):
        """更新任务状态"""
        pass
    
    def add_agent_run(self, run_id: str, task_id: str, agent_id: str,
                      input_data: str, output: str = None, 
                      status: str = "pending", metadata: dict = None):
        """添加 Agent 执行记录"""
        pass
    
    def add_event(self, event_id: str, task_id: str, event_type: str,
                  agent_id: str, payload: dict):
        """添加事件日志"""
        pass
    
    def get_task_events(self, task_id: str) -> List[dict]:
        """获取任务事件历史"""
        pass
```

#### 6.3.4 EventBus 接口

```python
class EventBus:
    """事件总线接口"""
    
    async def start(self):
        """启动事件总线"""
        pass
    
    async def stop(self):
        """停止事件总线"""
        pass
    
    def subscribe(self, topic: str, handler: Callable[[Event], None]):
        """订阅主题"""
        pass
    
    def unsubscribe(self, topic: str, handler: Callable = None):
        """取消订阅"""
        pass
    
    async def publish(self, topic: str, event_type: str, 
                      producer: str, payload: dict):
        """发布事件"""
        pass
```

---

## 七、实施时间表

### 7.1 详细时间表

| 天数 | 阶段 | 任务 | 工时 | 产出物 |
|------|------|------|------|--------|
| **Day 1** | Phase 1 | 任务 1.1 配置结构扩展 | 2h | config.py 修改 |
| | | 任务 1.2 模式切换命令 | 3h | /mode 命令 |
| | | 任务 1.3 Agent角色加载器 | 4h | agent_loader.py |
| **Day 2** | Phase 1 | 任务 1.4 基础调度器框架 | 6h | orchestrator.py, agent_pool.py |
| | | Phase 1 测试验证 | 2h | 测试用例 |
| **Day 3** | Phase 2 | 任务 2.1 消息分类器 | 4h | classifier.py |
| | | 任务 2.2 工作流引擎（上） | 4h | workflow.py（框架） |
| **Day 4** | Phase 2 | 任务 2.2 工作流引擎（下） | 4h | workflow.py（完整） |
| | | 任务 2.3 Agent间调用适配 | 4h | delegate_tool.py 修改 |
| **Day 5** | Phase 2 | 任务 2.4 状态持久化 | 4h | state_manager.py |
| | | Phase 2 集成测试 | 3h | 端到端测试 |
| **Day 6** | Phase 3 | 任务 3.1 事件总线 | 4h | event_bus.py |
| | | 任务 3.2 审议封驳逻辑 | 3h | workflow.py 增强 |
| **Day 7** | Phase 3 | 任务 3.3 错误处理与重试 | 3h | error_handler.py |
| | | 任务 3.4 日志与审计 | 2h | audit.py |
| | | Phase 3 测试验证 | 2h | 测试用例 |
| **Day 8** | Phase 4 | 任务 4.1 Dashboard API | 6h | dashboard/api.py |
| **Day 9** | Phase 4 | 任务 4.2 WebSocket推送 | 5h | websocket_handler.py |
| | | 文档编写 | 2h | README, API文档 |
| **Day 10** | Phase 4 | 任务 4.3 Redis事件总线（可选）| 4h | event_bus.py 扩展 |
| | | 全系统测试 | 3h | 集成测试 |
| **Day 11-13** | Buffer | 问题修复、优化、文档 | - | 稳定版本 |

---

### 7.2 里程碑定义

| 里程碑 | 完成时间 | 标准 |
|--------|----------|------|
| **M1: 基础框架可用** | Day 2 | 可以切换模式，加载 Agent 定义 |
| **M2: 核心流程跑通** | Day 5 | 三省六部流程完整执行 |
| **M3: 功能完善** | Day 7 | 错误处理、审计日志完成 |
| **M4: Dashboard 可用** | Day 9 | 可通过 API 查看任务状态 |
| **M5: 生产就绪** | Day 13 | 所有测试通过，文档完整 |

---

### 7.3 依赖关系图

```
Phase 1 (基础框架)
    │
    ├── config.py ────────┐
    ├── commands.py ──────┤
    ├── agent_loader.py ──┤
    └── orchestrator.py ──┴──▶ Phase 2 可开始
                                │
                                ├── classifier.py
                                ├── workflow.py ────┐
                                ├── delegate_tool ──┤
                                └── state_manager ──┴──▶ Phase 3 可开始
                                                          │
                                                          ├── event_bus.py
                                                          ├── error_handler.py
                                                          └── audit.py ────┴──▶ Phase 4 可开始
                                                                              │
                                                                              ├── dashboard/api.py
                                                                              └── websocket.py
```

---

### 7.4 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| delegate_tool 兼容问题 | 高 | 中 | 提前测试接口适配 |
| LLM 响应不稳定 | 中 | 高 | 添加重试和超时机制 |
| Agent 间调用复杂 | 高 | 中 | 先实现简单流程，逐步增强 |
| 状态同步问题 | 中 | 低 | 使用事件总线保证一致性 |
| 性能瓶颈 | 中 | 低 | Phase 4 引入 Redis |

---

## 八、验收标准

### 8.1 Phase 1 完成标准

- [ ] `/mode three_provinces` 可以切换模式
- [ ] `/mode default` 可以切回默认模式
- [ ] `/mode status` 显示当前模式状态
- [ ] 11 个 Agent 定义可以正常加载
- [ ] Orchestrator 可以初始化
- [ ] 配置持久化保存

### 8.2 Phase 2 完成标准

- [ ] 问候语正确识别为闲聊并友好回复
- [ ] 任务指令正确识别为旨意并创建任务
- [ ] 中书省可以起草方案
- [ ] 门下省可以审议方案（准奏/封驳）
- [ ] 尚书省可以派发任务
- [ ] 六部可以执行具体任务
- [ ] 任务状态正确持久化
- [ ] Agent 间调用权限正确检查

### 8.3 Phase 3 完成标准

- [ ] 审议最多 3 轮
- [ ] 封驳后可以修改重试
- [ ] 第 3 轮强制通过
- [ ] 错误可以正确处理和重试
- [ ] 事件日志完整可查
- [ ] 审计报告可以生成

### 8.4 Phase 4 完成标准

- [ ] `GET /tasks` API 返回任务列表
- [ ] `GET /tasks/{id}` API 返回任务详情
- [ ] `GET /tasks/{id}/events` API 返回事件历史
- [ ] WebSocket 可以实时接收进度
- [ ] Redis 事件总线可选启用

### 8.5 最终验收

- [ ] 完整流程：用户消息 → 分类 → 规划 → 审议 → 执行 → 报告
- [ ] 闲聊模式：问候语友好回复
- [ ] 旨意模式：完整三省六部流程
- [ ] 错误处理：重试、超时、回滚
- [ ] 可观测性：Dashboard、日志、审计
- [ ] 文档完整：README、API文档、架构图

---

## 附录

### A. 配置示例

```yaml
# ~/.hermes/config.yaml

multi_agent:
  enabled: true
  mode: "three_provinces"
  
  agents:
    taizi:
      enabled: true
      model: ""
    zhongshu:
      enabled: true
      model: "anthropic/claude-sonnet-4"  # 可为特定Agent指定模型
    menxia:
      enabled: true
      model: ""
    shangshu:
      enabled: true
      model: ""
    gongbu:
      enabled: true
      model: "deepseek/deepseek-coder"  # 代码任务用编程模型
  
  workflow:
    max_review_rounds: 3
    auto_approve_final: true
    timeout_per_agent: 300
  
  state:
    backend: "sqlite"
  
  event_bus:
    backend: "memory"
```

### B. API 使用示例

```bash
# 查看任务列表
curl http://localhost:8765/tasks

# 查看任务详情
curl http://localhost:8765/tasks/TASK-20260416-ABC123

# 查看任务事件
curl http://localhost:8765/tasks/TASK-20260416-ABC123/events

# 获取审计报告
curl http://localhost:8765/tasks/TASK-20260416-ABC123/audit
```

### C. WebSocket 使用示例

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8765/ws/tasks/TASK-20260416-ABC123');

// 接收事件
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.type}] ${data.agent_id}: ${data.progress || data.thought}`);
};

// 事件类型
// - progress: 进度更新
// - thought: 思考过程
// - status_change: 状态变更
// - agent_call: Agent调用
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-16  
**作者**: Hermes Agent
