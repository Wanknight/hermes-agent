# 三省六部多Agent系统 - 落地执行方案

## 一、执行概览

### 总体策略
- **分阶段迭代**：每个Phase完成后进行验收测试
- **最小可用优先**：先实现核心流程，再完善功能
- **复用现有代码**：最大程度复用 Hermes 现有基础设施

### 里程碑

| 里程碑 | 时间 | 交付物 | 验收标准 |
|--------|------|--------|----------|
| **M1** | Day 2 | 基础框架 | `/mode` 命令可用，Agent 定义可加载 |
| **M2** | Day 5 | 核心流程 | 完整三省六部流程可执行 |
| **M3** | Day 7 | 功能完善 | 错误处理、审计日志完成 |
| **M4** | Day 9 | Dashboard | API 和 WebSocket 可用 |
| **M5** | Day 13 | 生产就绪 | 全部测试通过 |

---

## 二、Phase 1：基础框架

### 任务清单

#### 任务 1.1：配置结构扩展
**文件**：`hermes_cli/config.py`  
**工时**：2小时  
**验收**：`multi_agent` 配置块可加载

**具体修改**：
1. 在 `DEFAULT_CONFIG` 添加 `multi_agent` 配置块
2. 更新 `_config_version` 从 5 → 6
3. 添加迁移函数处理旧配置

---

#### 任务 1.2：模式切换命令
**文件**：`hermes_cli/commands.py`, `cli.py`  
**工时**：3小时  
**验收**：`/mode` 命令可以切换模式

**具体修改**：
1. 在 `COMMAND_REGISTRY` 添加 `mode` 命令定义
2. 在 `cli.py` 的 `process_command()` 添加处理逻辑
3. 实现模式切换和持久化

---

#### 任务 1.3：Agent 角色加载器
**文件**：`multi_agent/__init__.py`, `multi_agent/agent_loader.py`  
**工时**：4小时  
**验收**：可以从 YAML 加载 Agent 定义

**具体修改**：
1. 创建 `multi_agent/` 目录
2. 实现 `AgentRole` 数据类
3. 实现 `AgentLoader` 加载器
4. 支持内置定义和用户自定义

---

#### 任务 1.4：基础调度器框架
**文件**：`multi_agent/orchestrator.py`, `multi_agent/agent_pool.py`  
**工时**：6小时  
**验收**：调度器可以初始化并创建任务

**具体修改**：
1. 实现 `TaskContext` 数据类
2. 实现 `MultiAgentOrchestrator` 核心类
3. 实现 `AgentPool` 角色池管理
4. 与现有 `delegate_tool` 集成

---

## 三、Phase 2：核心流程

### 任务清单

#### 任务 2.1：消息分类器
**文件**：`multi_agent/classifier.py`  
**工时**：4小时  
**验收**：正确区分闲聊和旨意

---

#### 任务 2.2：工作流引擎
**文件**：`multi_agent/workflow.py`  
**工时**：8小时  
**验收**：完整流程可执行

---

#### 任务 2.3：Agent 间调用适配
**文件**：`tools/delegate_tool.py`  
**工时**：4小时  
**验收**：Agent 可以相互调用

---

#### 任务 2.4：状态持久化
**文件**：`multi_agent/state_manager.py`  
**工时**：4小时  
**验收**：任务状态正确保存和读取

---

## 四、Phase 3：完善功能

### 任务清单

#### 任务 3.1：事件总线
**文件**：`multi_agent/event_bus.py`  
**工时**：4小时  
**验收**：事件可以发布和订阅

---

#### 任务 3.2：审议封驳逻辑
**文件**：`multi_agent/workflow.py`  
**工时**：4小时  
**验收**：最多3轮审议，强制通过

---

#### 任务 3.3：错误处理
**文件**：`multi_agent/error_handler.py`  
**工时**：4小时  
**验收**：错误可以重试和恢复

---

#### 任务 3.4：日志审计
**文件**：`multi_agent/audit.py`  
**工时**：2小时  
**验收**：审计报告可生成

---

## 五、Phase 4：Dashboard（可选）

### 任务清单

#### 任务 4.1：REST API
**文件**：`multi_agent/dashboard/api.py`  
**工时**：8小时  
**验收**：API 正常响应

---

#### 任务 4.2：WebSocket 推送
**文件**：`multi_agent/dashboard/websocket_handler.py`  
**工时**：6小时  
**验收**：实时进度推送

---

## 六、文件创建清单

### 新建文件

```
multi_agent/
├── __init__.py
├── orchestrator.py
├── agent_pool.py
├── agent_loader.py
├── workflow.py
├── classifier.py
├── event_bus.py
├── state_manager.py
├── error_handler.py
├── audit.py
└── agents/
    ├── taizi.yaml
    ├── zhongshu.yaml
    ├── menxia.yaml
    ├── shangshu.yaml
    ├── hubu.yaml
    ├── bingbu.yaml
    ├── libu.yaml
    ├── xingbu.yaml
    ├── gongbu.yaml
    ├── libu_hr.yaml
    └── zaochao.yaml
```

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `hermes_cli/config.py` | 添加 multi_agent 配置块 |
| `hermes_cli/commands.py` | 添加 /mode 命令定义 |
| `cli.py` | 添加模式切换处理 |
| `tools/delegate_tool.py` | 支持 multi-agent 调用 |

---

## 七、验收测试清单

### Phase 1 验收
- [ ] `/mode` 显示当前模式
- [ ] `/mode default` 切换到默认模式
- [ ] `/mode three_provinces` 切换到三省六部模式
- [ ] `/mode status` 显示详细状态
- [ ] 11个 Agent 定义正常加载
- [ ] 配置持久化保存

### Phase 2 验收
- [ ] 问候语识别为闲聊
- [ ] 任务指令识别为旨意
- [ ] 中书省可以制定方案
- [ ] 门下省可以审议方案
- [ ] 尚书省可以派发任务
- [ ] 六部可以执行任务
- [ ] 任务状态正确持久化

### Phase 3 验收
- [ ] 审议最多3轮
- [ ] 封驳后可修改重试
- [ ] 第3轮强制通过
- [ ] 错误可以重试
- [ ] 审计报告可生成

---

**创建时间**: 2026-04-16  
**预计完成**: 2026-04-29
