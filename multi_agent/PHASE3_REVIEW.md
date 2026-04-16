# 三省六部多Agent系统 - Phase 3 审查报告

> 版本：v2.0  
> 日期：2026-04-16  
> 状态：**P0问题已修复，进入P1阶段**

---

## 一、Phase 1-2 审查结果

### 1.1 完成状态总览

| 组件 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 配置扩展 | `hermes_cli/config.py` | ✅ 完成 | multi_agent配置块、版本迁移 |
| 模式命令 | `cli.py`, `commands.py` | ✅ 完成 | `/mode` 命令实现 |
| Agent定义 | `multi_agent/agents/*.yaml` | ✅ 完成 | 11个Agent定义完整 |
| Agent加载 | `agent_loader.py` | ✅ 完成 | YAML加载、权限解析 |
| Agent池 | `agent_pool.py` | ✅ 完成 | LLM调用、Agent间调用 |
| 调度器 | `orchestrator.py` | ✅ 完成 | 主流程、审议封驳 |
| CLI集成 | `cli.py` | ✅ 完成 | 模式切换、消息路由 |

### 1.2 Phase 1-2 验收标准对照

#### Phase 1 验收 ✅ 全部通过

- [x] `/mode three_provinces` 可以切换模式
- [x] `/mode default` 可以切回默认模式
- [x] `/mode status` 显示当前模式状态
- [x] 11 个 Agent 定义可以正常加载
- [x] Orchestrator 可以初始化
- [x] 配置持久化保存

#### Phase 2 验收 ✅ 全部通过

- [x] 问候语正确识别为闲聊并友好回复
- [x] 任务指令正确识别为旨意并创建任务
- [x] 中书省可以起草方案
- [x] 门下省可以审议方案（准奏/封驳）
- [x] 尚书省可以派发任务
- [x] 六部可以执行具体任务
- [x] Agent 间调用权限正确检查

---

## 二、P0 问题修复记录

### 2.1 问题1：Agent间调用 ✅ 已修复

**原始问题**：尚书省无法真正派发给六部，只能自己执行

**修复方案**：
1. 在 `agent_pool.py` 中添加 `dispatch_to_agent()` 和 `dispatch_parallel()` 方法
2. 在 `orchestrator.py` 中重写 `_execute_plan()` 方法
3. 解析尚书省的派发决策，调用 `dispatch_to_agent()` 派发给六部

**修复后流程**：
```
尚书省收到方案 → 分析需要哪些部门 → 输出 dispatches 列表
                                          ↓
                              调用 dispatch_to_agent()
                                          ↓
                              工部/兵部/户部等执行 → 返回结果
```

**代码变更**：
- `agent_pool.py`: +100行（dispatch_to_agent, dispatch_parallel, _get_callable_agents）
- `orchestrator.py`: `_execute_plan()` 重写，新增 `_parse_dispatch_decision()`, `_has_error()`

### 2.2 问题2：审议封驳逻辑 ✅ 已修复

**原始问题**：门下省封驳后无后续动作，审议形同虚设

**修复方案**：
1. 在 `_review_plan()` 中处理 rejected 情况
2. 新增 `_revise_plan()` 方法调用中书省修改方案
3. 将审议意见传递给中书省作为修改依据

**修复后流程**：
```
门下省封驳 → 提取审议意见（comments, issues, suggestions）
                    ↓
         调用 _revise_plan() → 中书省修改方案
                    ↓
         更新 task.plan → 重新提交审议
                    ↓
         最多3轮，最后一轮强制通过
```

**代码变更**：
- `orchestrator.py`: `_review_plan()` 更新，新增 `_revise_plan()` 方法（+65行）

---

## 三、Phase 3 实施方案

### 3.1 Phase 3 目标

| 任务 | 优先级 | 预计工时 | 状态 |
|------|--------|----------|------|
| 事件总线（内存版） | P2 | 4h | 待开始 |
| 审议封驳完善 | P0 | ✅ 已完成 | 2h |
| 错误处理与重试 | P1 | 3h | 待开始 |
| 日志与审计 | P1 | 2h | 待开始 |

### 3.2 剩余P1任务详解

#### P1-1：任务状态持久化

**目标**：SQLite存储任务状态，支持恢复和查询

**新建文件**：`multi_agent/state_manager.py`

**核心接口**：
```python
class MultiAgentStateManager:
    def create_task(self, task_id, title, creator, metadata) -> dict
    def get_task(self, task_id) -> Optional[dict]
    def update_task_status(self, task_id, status, current_agent)
    def add_agent_run(self, run_id, task_id, agent_id, input_data, output, status)
    def add_event(self, event_id, task_id, event_type, agent_id, payload)
    def get_task_events(self, task_id) -> List[dict]
    def list_tasks(self, status, limit) -> List[dict]
```

**数据库表结构**：
```sql
CREATE TABLE ma_tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT,
    current_agent TEXT,
    creator TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSON
);

CREATE TABLE ma_agent_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT,
    agent_id TEXT,
    input TEXT,
    output TEXT,
    status TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE ma_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT,
    event_type TEXT,
    agent_id TEXT,
    payload JSON,
    created_at TIMESTAMP
);
```

**实施步骤**：
1. 创建 `state_manager.py` 文件
2. 实现 SQLite 表创建和迁移
3. 实现各接口方法
4. 在 `orchestrator.py` 中集成状态持久化
5. 添加任务恢复逻辑

**验证标准**：
- [ ] 任务可以创建和读取
- [ ] 状态可以更新
- [ ] 事件日志可以添加
- [ ] 历史可以回溯
- [ ] 数据库文件正确创建（`~/.hermes/multi_agent.db`）

#### P1-2：任务进度反馈

**目标**：实时显示任务执行进度

**实现方式**：
1. 在 CLI 中显示当前执行阶段
2. 使用 Rich Panel 显示进度
3. 显示当前 Agent 和预计剩余时间

**进度状态**：
```python
PROGRESS_STAGES = {
    "classifying": ("🔍 分类中", "太子"),
    "planning": ("📝 规划中", "中书省"),
    "reviewing": ("⚖️ 审议中", "门下省"),
    "dispatching": ("📤 派发中", "尚书省"),
    "executing": ("⚡ 执行中", "六部"),
    "completed": ("✅ 已完成", None),
}
```

**实施步骤**：
1. 在 `TaskContext` 中添加 `progress` 字段
2. 在各阶段更新进度
3. 在 CLI 显示进度面板
4. 支持任务列表查看（`/tasks` 命令）

---

## 四、Phase 4 可选增强（待规划）

| 功能 | 描述 | 优先级 | 依赖 |
|------|------|--------|------|
| Dashboard API | REST API 查看任务状态 | P2 | Phase 3 |
| WebSocket 推送 | 实时进度推送 | P2 | 事件总线 |
| Redis 事件总线 | 分布式事件支持 | P3 | Redis 安装 |
| 错误重试增强 | 智能重试、熔断 | P2 | 错误处理 |

---

## 五、当前系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Hermes Agent Core                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  用户消息                                                    │
│      │                                                       │
│      ▼                                                       │
│  ┌─────────────┐                                             │
│  │   /mode     │ ← 模式切换命令                              │
│  │  切换检查   │                                             │
│  └─────────────┘                                             │
│      │                                                       │
│      ▼                                                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            MultiAgentOrchestrator                     │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 太子 (taizi) → 分类 (chat/decree)              │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │            │ decree                                   │  │
│  │            ▼                                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 中书省 (zhongshu) → 规划方案                   │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │            │                                           │  │
│  │            ▼                                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 门下省 (menxia) → 审议 (approved/rejected)     │ │  │
│  │  │   └ rejected → 中书省修改方案 → 重新审议       │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │            │ approved                                  │  │
│  │            ▼                                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 尚书省 (shangshu) → 派发决策                   │ │  │
│  │  │   └ dispatch_to_agent() → 六部执行            │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │            │                                           │  │
│  │            ▼                                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 六部执行:                                       │ │  │
│  │  │  • 工部 (gongbu) - 代码开发                    │ │  │
│  │  │  • 兵部 (bingbu) - 基础设施                    │ │  │
│  │  │  • 户部 (hubu) - 数据处理                      │ │  │
│  │  │  • 礼部 (libu) - 文档撰写                      │ │  │
│  │  │  • 刑部 (xingbu) - 审查测试                    │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │            │                                           │  │
│  │            ▼                                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 汇总报告 → 返回用户                            │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ AgentPool (agent_pool.py)                             │  │
│  │  • execute() - 执行单个Agent                          │  │
│  │  • dispatch_to_agent() - Agent间调用 ✅               │  │
│  │  • dispatch_parallel() - 并行派发 ✅                  │  │
│  │  • can_call() - 权限检查                              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 状态管理 (待实现 P1-1)                                │  │
│  │  • SQLite 持久化                                      │  │
│  │  • 任务恢复                                           │  │
│  │  • 历史查询                                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、结论与下一步

### 6.1 当前状态

✅ **Phase 1 完成** - 框架搭建  
✅ **Phase 2 完成** - LLM调用集成  
✅ **P0 问题修复** - Agent间调用、审议封驳  

### 6.2 下一步工作

| 优先级 | 任务 | 预计工时 |
|--------|------|----------|
| P1-1 | SQLite 状态持久化 | 3h |
| P1-2 | 任务进度反馈 | 2h |
| P2 | 事件总线（内存版） | 4h |
| P2 | 错误处理增强 | 3h |

**总计剩余工时：约 12h**

### 6.3 建议执行顺序

1. **先完成 P1-1（状态持久化）** - 这是其他功能的基础
2. **再完成 P1-2（进度反馈）** - 提升用户体验
3. **最后完成 P2 功能** - 性能和健壮性优化

---

**报告完成时间**：2026-04-16  
**下次审查节点**：P1任务完成后
