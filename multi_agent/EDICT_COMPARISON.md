# 三省六部多Agent系统 - Edict 对比分析报告

> **版本**: v1.0  
> **日期**: 2026-04-16  
> **目的**: 对比当前实现与 Edict 开源项目的功能差异，确定下一步最优路径

---

## 一、项目概况对比

| 维度 | Edict (开源) | 当前实现 (Hermes内置) |
|------|-------------|---------------------|
| **定位** | 独立产品 | Hermes Agent 内置模式 |
| **Agent数量** | 12个 (11业务+1兼容) | 11个 |
| **前端** | React 18 + TypeScript | 无 (CLI/Gateway) |
| **后端** | Python stdlib | 集成于 Hermes |
| **事件总线** | Redis Streams | InMemoryEventBus |
| **数据库** | PostgreSQL | SQLite |
| **部署方式** | Docker/systemd | Hermes 启动即用 |

---

## 二、核心功能对比

### 2.1 Agent架构

| 特性 | Edict | 当前实现 | 差距 |
|------|-------|----------|------|
| 太子分拣 | ✅ chat/decree | ✅ 已实现 | 无 |
| 中书规划 | ✅ DAG分解 | ✅ 已实现 | 无 |
| 门下审议 | ✅ 封驳循环 | ✅ 已实现 | 无 |
| 尚书派发 | ✅ 并行派发 | ✅ 已实现 | 无 |
| 六部执行 | ✅ 6部 | ✅ 已实现 | 无 |
| Agent间调用 | ✅ 权限控制 | ✅ 已实现 | 无 |

**结论**: 核心Agent架构已完全对齐。

### 2.2 任务生命周期

| 状态 | Edict | 当前实现 | 差距 |
|------|-------|----------|------|
| 待分拣 | ✅ | ✅ CLASSIFYING | 无 |
| 规划中 | ✅ | ✅ PLANNING | 无 |
| 审议中 | ✅ | ✅ REVIEWING | 无 |
| 已派发 | ✅ | ✅ DISPATCHED | 无 |
| 执行中 | ✅ | ✅ EXECUTING | 无 |
| 待审查 | ✅ | ❌ 缺失 | **需补充** |
| 已完成 | ✅ | ✅ COMPLETED | 无 |
| 已阻塞 | ✅ | ❌ 缺失 | **需补充** |
| 任务干预 | ✅ 停止/取消/恢复 | ❌ 缺失 | **需补充** |

### 2.3 可观测性

| 特性 | Edict | 当前实现 | 差距 |
|------|-------|----------|------|
| 实时看板 | ✅ 10面板 | ❌ 无 | **大差距** |
| 任务看板 | ✅ Kanban | ❌ CLI /tasks | **大差距** |
| Agent健康监控 | ✅ 心跳检测 | ⚠️ 基础统计 | 需增强 |
| Token消耗统计 | ✅ 排行榜 | ✅ 已实现 | 无 |
| 审计日志 | ✅ 完整存档 | ✅ ma_audit_log | 无 |
| 事件历史 | ✅ Redis持久化 | ✅ 内存历史 | 可扩展 |
| 奏折存档 | ✅ Markdown导出 | ❌ 缺失 | **需补充** |

### 2.4 Dashboard功能 (Edict独有)

| 面板 | 功能 | 当前实现 | 优先级 |
|------|------|----------|--------|
| 📋 旨意看板 | 任务卡片、过滤、干预 | ❌ | **高** |
| 🔭 省部调度 | 可视化流程图 | ❌ | 中 |
| 📜 奏折阁 | 存档+时间线 | ❌ | 中 |
| 📜 旨库 | 9个预设模板 | ❌ | 低 |
| 👥 官员总览 | Token排行榜 | ⚠️ 基础 | 低 |
| 📰 天下要闻 | 新闻聚合 | ❌ | 低 |
| ⚙️ 模型配置 | 热切换LLM | ❌ | 中 |
| 🛠️ 技能配置 | 查看添加Skills | ❌ | 低 |
| 💬 小任务 | Session监控 | ❌ | 低 |
| 🏛️ 朝堂议政 | 多Agent辩论 | ❌ | 低 |

### 2.5 技术差异

| 维度 | Edict | 当前实现 | 建议 |
|------|-------|----------|------|
| **事件总线** | Redis Streams | InMemory | 可扩展Redis |
| **数据库** | PostgreSQL | SQLite | 够用 |
| **前端** | React SPA | 无 | 需开发 |
| **部署** | 独立服务 | 内置模式 | 各有优势 |
| **消息推送** | Webhook/Feishu | Gateway已支持 | 无需重复 |

---

## 三、差距分析

### 3.1 已对齐功能 (约70%)

- ✅ 核心三省六部流程
- ✅ Agent间调用权限
- ✅ 审议封驳循环
- ✅ 状态持久化
- ✅ 审计日志
- ✅ 错误重试/熔断
- ✅ 事件总线(内存版)
- ✅ 输出解析增强

### 3.2 未对齐功能 (约30%)

#### 高优先级

| 功能 | 差距 | 工时 | 说明 |
|------|------|------|------|
| 任务干预 | 缺失 | 4h | 停止/取消/恢复任务 |
| 阻塞状态 | 缺失 | 2h | 任务可被阻塞等待 |
| 待审查状态 | 缺失 | 1h | 六部执行后需要审查 |

#### 中优先级

| 功能 | 差距 | 工时 | 说明 |
|------|------|------|------|
| Dashboard API | 缺失 | 4h | REST API对外暴露 |
| 奏折存档 | 缺失 | 2h | Markdown导出 |
| 任务模板 | 缺失 | 3h | 预设任务模板 |

#### 低优先级

| 功能 | 差距 | 工时 | 说明 |
|------|------|------|------|
| 可视化看板 | 缺失 | 40h+ | React前端开发 |
| 新闻聚合 | 缺失 | 4h | 非核心功能 |
| 朝堂议政 | 缺失 | 8h | 多Agent辩论 |

---

## 四、战略决策

### 4.1 定位差异

| 维度 | Edict | 当前实现 |
|------|-------|----------|
| **目标用户** | 非技术用户 | 开发者/技术用户 |
| **使用方式** | Web UI | CLI/IM消息 |
| **集成度** | 独立部署 | 深度集成Hermes |
| **扩展性** | 框架级 | Agent内部模式 |

### 4.2 核心优势

**Edict优势**:
- 完整的可视化Dashboard
- 非技术用户友好
- 一键Docker部署

**当前实现优势**:
- 无需独立部署，开箱即用
- 深度集成Hermes工具链
- Gateway多平台支持(飞书/微信/Telegram)
- 更轻量，零依赖

### 4.3 是否需要调整？

**结论: 不需要大调整，但需要补齐关键缺失功能**

理由:
1. **定位不同**: 当前实现是Hermes内置模式，不是独立产品
2. **用户不同**: 面向开发者，CLI/IM交互足够
3. **复用已有**: Gateway已支持多平台，无需重复开发Dashboard
4. **补齐核心**: 任务干预、阻塞状态是核心功能，需要补充

---

## 五、下一步建议

### 5.1 P3 实施计划（修订）

| 优先级 | 任务 | 工时 | 价值 |
|--------|------|------|------|
| **P3-0** | 任务工作空间 | 4h | 🔥 核心缺失 - 产出持久化 |
| **P3-1** | 任务干预功能 | 4h | 核心功能补齐 |
| **P3-2** | 阻塞/待审查状态 | 3h | 完善状态机 |
| **P3-3** | Dashboard API | 4h | 对外暴露接口 |
| **P3-4** | 奏折存档导出 | 2h | 可观测性增强 |

**总工时: 17h**

---

## 六、P3-0 任务工作空间设计

### 6.1 问题分析

**当前问题**:
1. 各环节产出只存 JSON 文本，实际文件丢失
2. 环节间无法共享文件资源（如户部的数据给工部用）
3. 无法追溯任务的实际产出文件

**Edict 做法**:
- 每个任务有独立工作空间目录
- 各 Agent 产出保存到子目录
- 通过文件路径传递资源

### 6.2 设计方案

#### 目录结构

```
~/.hermes/tasks/
└── task-20260416-001/
    ├── .task.json              # 任务元数据
    ├── classification.json     # 太子分类结果
    ├── plan.md                 # 中书省规划文档
    ├── review.json             # 门下省审议结果
    ├── dispatch.json           # 尚书省派发决策
    ├── outputs/                # 各部门产出目录
    │   ├── hubu/
    │   │   └── data.csv
    │   ├── gongbu/
    │   │   └── main.py
    │   ├── libu/
    │   │   └── report.md
    │   ├── bingbu/
    │   └── xingbu/
    └── final/
        └── summary.md          # 最终汇总报告
```

#### 核心接口

```python
class TaskWorkspace:
    """任务工作空间管理"""
    
    def __init__(self, task_id: str, base_path: Path = None):
        self.task_id = task_id
        self.base_path = base_path or get_hermes_home() / "tasks"
        self.workspace_path = self.base_path / task_id
    
    def create(self) -> Path:
        """创建工作空间目录结构"""
        
    def save_stage_output(self, stage: str, content: Any, filename: str = None) -> Path:
        """保存阶段产出
        
        stage: 'classification', 'plan', 'review', 'dispatch', 'hubu', 'gongbu'...
        """
        
    def get_stage_output(self, stage: str, filename: str = None) -> Optional[str]:
        """读取阶段产出"""
        
    def list_outputs(self, agent_id: str = None) -> List[Path]:
        """列出产出文件"""
        
    def get_output_path(self, agent_id: str, filename: str) -> Path:
        """获取指定Agent的产出文件路径"""
        
    def save_final(self, content: str, filename: str = "summary.md") -> Path:
        """保存最终结果"""
```

#### 资源传递机制

```python
# 中书省规划时，指定产出路径
plan = {
    "analysis": "...",
    "steps": [
        {
            "step": 1,
            "agent": "hubu", 
            "task": "处理用户数据",
            "output_file": "data.csv"  # 保存到 outputs/hubu/data.csv
        },
        {
            "step": 2,
            "agent": "gongbu",
            "task": "编写分析脚本",
            "input_files": ["hubu/data.csv"],  # 读取户部产出
            "output_file": "analyze.py"
        },
        {
            "step": 3, 
            "agent": "libu",
            "task": "撰写分析报告",
            "input_files": ["hubu/data.csv", "gongbu/analyze.py"],
            "output_file": "report.md"
        }
    ]
}
```

#### Agent 执行上下文

```python
# 执行时传入工作空间信息
context = {
    "workspace_path": "/path/to/tasks/task-xxx",
    "output_dir": "/path/to/tasks/task-xxx/outputs/gongbu",
    "input_files": ["/path/to/tasks/task-xxx/outputs/hubu/data.csv"],
    "agent_id": "gongbu"
}
```

### 6.3 实施计划

| 步骤 | 文件 | 改动 |
|------|------|------|
| 1 | 新建 `task_workspace.py` | 工作空间管理类 |
| 2 | `orchestrator.py` | 创建任务时初始化工作空间 |
| 3 | `TaskContext` | 添加 `workspace_path` 字段 |
| 4 | `agent_pool.py` | 执行时传入工作空间路径到 context |
| 5 | Agent prompts | 引导保存文件到指定目录 |
| 6 | 测试验证 | 确保实际产出可追溯 |

### 6.4 验收标准

- [ ] 任务创建时自动创建工作空间目录
- [ ] 各阶段产出保存到对应文件（非仅 JSON）
- [ ] Agent 可读取上游产出的文件
- [ ] `/tasks <id> files` 可列出所有产出文件
- [ ] 测试用例验证端到端流程

### 5.2 暂缓功能

| 功能 | 原因 |
|------|------|
| 可视化Dashboard | Gateway已支持多平台，投入产出比低 |
| 新闻聚合 | 非核心功能 |
| 朝堂议政 | 非核心功能 |
| 任务模板 | 可后期补充 |

### 5.3 建议实施顺序

```
Week 1: P3-1 任务干预 (4h)
  ├─ 停止任务: /tasks <id> stop
  ├─ 取消任务: /tasks <id> cancel
  └─ 恢复任务: /tasks <id> resume

Week 2: P3-2 阻塞/待审查状态 (3h)
  ├─ BLOCKED 状态
  ├─ PENDING_REVIEW 状态
  └─ 状态转换逻辑

Week 3: P3-3 Dashboard API (4h)
  ├─ GET /api/tasks
  ├─ GET /api/tasks/:id
  ├─ POST /api/tasks/:id/stop
  └─ WebSocket 推送

Week 4: P3-4 奏折存档 (2h)
  ├─ Markdown生成
  └─ /tasks <id> export
```

---

## 六、总结

### 当前状态

- ✅ 核心三省六部流程 100% 对齐
- ✅ P1/P2 基础设施完成
- ⚠️ 任务状态机缺少 2 个状态
- ❌ 任务干预功能缺失
- ❌ Dashboard API 未开发

### 关键结论

1. **不需要开发完整Dashboard** - Gateway已支持多平台
2. **优先补齐任务干预** - 这是核心功能差距
3. **Dashboard API 可选** - 如需第三方集成再开发
4. **Redis事件总线可延后** - 单机场景内存版够用

### 下一步行动

**推荐立即开始 P3-1 任务干预功能** (4h工时)

---

**文档完成时间**: 2026-04-16
**下次审查节点**: P3任务完成后
