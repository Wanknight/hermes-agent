# 聊天终端 Dashboard 实施方案

> **版本**: v1.0  
> **日期**: 2026-04-16  
> **目的**: 在微信/飞书终端实现多Agent任务的查询、推送、报告功能

---

## 一、需求确认

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 推送渠道 | 原对话 (origin) | 任务通知推送到用户发起对话的位置 |
| 推送级别 | 关键节点 | 仅推送重要的任务状态变更 |
| 日报时间 | 每天 09:30 | 自动推送每日统计报告 |
| 周报时间 | 每周一 09:30 | 自动推送每周统计报告 |
| 飞书格式 | Markdown 卡片 | 支持表格、列表、标题 |
| 微信格式 | 纯文本卡片 | 简化格式，无 Markdown |

---

## 二、查询指令设计

### 2.1 指令清单

| 指令 | 功能 | 说明 |
|------|------|------|
| `/tasks` | 任务列表 | 显示最近 10 条任务卡片 |
| `/tasks stats` | 统计面板 | 总体数据概览 + Agent 排行 |
| `/tasks stats daily` | 日报统计 | 今日数据详情 |
| `/tasks stats weekly` | 周报统计 | 本周数据汇总 |
| `/tasks stats agents` | Agent排行 | Token消耗、调用次数排行 |
| `/tasks <id>` | 任务详情 | 单个任务完整信息卡片 |
| `/tasks <id> events` | 任务事件 | 执行过程时间线 |
| `/tasks <id> audit` | 审计日志 | Agent调用记录 |
| `/tasks <id> workspace` | 工作空间 | 产出文件列表 |
| `/tasks active` | 活跃任务 | 正在执行的任务列表 |
| `/tasks failed` | 失败任务 | 失败任务列表 |
| `/tasks help` | 帮助信息 | 显示指令用法 |

### 2.2 命令注册

**修改 `hermes_cli/commands.py`**：

```python
# 当前：cli_only=True
CommandDef("tasks", "List multi-agent tasks and their status", "Configuration",
           args_hint="[stats|<task_id>]",
           cli_only=True),

# 修改为：Gateway 可用
CommandDef("tasks", "List multi-agent tasks and their status", "Configuration",
           args_hint="[stats|<task_id>|active|failed|help]",
           subcommands=("stats", "active", "failed", "help")),
```

---

## 三、输出格式设计

### 3.1 任务列表卡片

#### 飞书 Markdown

```markdown
**📋 任务看板** `共 12 条`

---

**task-20260416-abc1**
> 状态：🔄 执行中 | 类型：旨意 | 工部
> 标题：编写API接口文档
> 创建：2026-04-16 10:30
> 进度：尚书省 → 工部执行

---

**task-20260416-def2**  
> 状态：✅ 已完成 | 类型：旨意 | 户部
> 标题：数据分析报告
> 创建：2026-04-16 09:15

---

`使用 /tasks <id> 查看详情`
```

#### 微信纯文本

```
📋 任务看板 (共 12 条)
━━━━━━━━━━━━━━━━━━━━
🔄 task-abc1 | 执行中 | 工部
   编写API接口文档

✅ task-def2 | 已完成 | 户部  
   数据分析报告

━━━━━━━━━━━━━━━━━━━━
使用 /tasks <id> 查看详情
```

### 3.2 统计面板卡片

#### 飞书 Markdown

```markdown
**📊 多Agent统计面板**

**总体概览**
| 指标 | 数值 |
|------|------|
| 总任务数 | 156 |
| 已完成 | 142 (91%) |
| 进行中 | 3 |
| 失败 | 11 (7%) |
| 平均耗时 | 4.2 分钟 |

**今日统计**
| 指标 | 数值 |
|------|------|
| 新增任务 | 8 |
| 完成任务 | 12 |
| Token消耗 | 45,230 |

**Agent 调用排行**
| 排名 | Agent | 调用次数 | Token |
|------|-------|----------|-------|
| 1 | 工部 | 45 | 12,340 |
| 2 | 户部 | 32 | 8,560 |
| 3 | 礼部 | 28 | 6,780 |
```

#### 微信纯文本

```
📊 多Agent统计面板
━━━━━━━━━━━━━━━━━━━━

【总体概览】
总任务数：156
已完成：142 (91%)
进行中：3
失败：11 (7%)
平均耗时：4.2 分钟

【今日统计】
新增任务：8
完成任务：12
Token消耗：45,230

【Agent 调用排行】
1. 工部 - 45次 - 12,340 token
2. 户部 - 32次 - 8,560 token
3. 礼部 - 28次 - 6,780 token
```

### 3.3 任务详情卡片

#### 飞书 Markdown

```markdown
**📝 任务详情**

**基本信息**
> 任务ID：`task-20260416-abc12345`
> 标题：编写API接口文档
> 状态：🔄 执行中
> 类型：旨意
> 创建：2026-04-16 10:30:15

**执行流程**
```
✅ 太子分拣 → 10:30:18
✅ 中书省规划 → 10:30:45  
✅ 门下省审议 → 10:31:02 (通过)
🔄 尚书省派发 → 10:31:15
   └─ 🔄 工部执行中...
```

**规划内容**
> 共 3 个步骤：
> 1. 设计API结构
> 2. 编写接口文档
> 3. 添加示例代码

**执行记录**
| Agent | 状态 | 耗时 | Token |
|-------|------|------|-------|
| 太子 | ✅ | 0.3s | 120 |
| 中书省 | ✅ | 15s | 850 |
| 门下省 | ✅ | 8s | 420 |
| 工部 | 🔄 | - | - |

`/tasks <id> events 查看事件流`
`/tasks <id> audit 查看审计日志`
`/tasks <id> workspace 查看产出文件`
```

#### 微信纯文本

```
📝 任务详情
━━━━━━━━━━━━━━━━━━━━

【基本信息】
ID：task-20260416-abc12345
标题：编写API接口文档
状态：🔄 执行中
类型：旨意
创建：2026-04-16 10:30:15

【执行流程】
✅ 太子分拣 → 10:30:18
✅ 中书省规划 → 10:30:45
✅ 门下省审议 → 10:31:02
🔄 尚书省派发 → 10:31:15
   └─ 🔄 工部执行中...

【执行记录】
太子 ✅ 0.3s 120token
中书省 ✅ 15s 850token
门下省 ✅ 8s 420token
工部 🔄 执行中

━━━━━━━━━━━━━━━━━━━━
/tasks <id> events 事件流
/tasks <id> audit 审计日志
/tasks <id> workspace 产出文件
```

### 3.4 任务事件卡片

#### 飞书 Markdown

```markdown
**📜 任务事件流** `task-20260416-abc1`

```
10:30:15 📥 任务创建
10:30:18 👑 太子分拣完成
         └─ 类型：旨意
         └─ 标题：编写API接口文档
10:30:45 📋 中书省规划完成
         └─ 步骤：3 个
         └─ 预计：工部、礼部
10:31:02 🔍 门下省审议通过
10:31:15 📤 尚书省派发
         └─ 工部：设计API结构
         └─ 礼部：编写文档
10:31:20 🔧 工部开始执行...
```
```

### 3.5 工作空间卡片

#### 飞书 Markdown

```markdown
**📁 任务工作空间** `task-20260416-abc1`

**路径**: `~/.hermes/tasks/task-20260416-abc1/`

**产出文件**
```
├── classification.json    # 太子分类结果
├── plan.json              # 中书省规划方案
├── review.json            # 门下省审议记录
├── outputs/
│   ├── gongbu/
│   │   └── api_design.md  # 工部产出
│   └── libu/
│       └── doc.md         # 礼部产出
└── final/
    └── summary.md         # 最终汇总
```

**文件大小**: 12.5 KB
```

---

## 四、关键节点推送

### 4.1 推送节点配置

| 节点 | 触发条件 | 图标 | 推送模板 |
|------|----------|------|----------|
| `task_started` | 旨意消息分类完成 | 📥 | 新任务：{标题} |
| `plan_completed` | 中书省规划完成 | 📋 | 规划完成：{步骤数}步 |
| `review_approved` | 门下省审议通过 | ✅ | 审议通过，开始执行 |
| `review_rejected` | 门下省封驳 | ⚠️ | 方案被封驳，重新规划 (第{n}轮) |
| `dispatched` | 尚书省派发六部 | 📤 | 已派发给：{部门列表} |
| `agent_completed` | 六部执行完成 | ✅ | {部门}完成：{摘要} |
| `task_completed` | 所有环节结束 | 🎉 | 任务完成！耗时 {duration} |
| `task_failed` | 任意环节出错 | ❌ | 任务失败：{原因} |

### 4.2 推送格式

#### 任务开始推送

```markdown
📥 **新任务开始**

> 标题：{title}
> 类型：旨意
> 时间：{time}

正在分拣处理...
```

#### 审议结果推送

```markdown
🔍 **门下省审议结果**

> 决定：✅ 通过
> 轮次：第 {round} 轮

方案已批准，即将派发执行。
```

```markdown
🔍 **门下省审议结果**

> 决定：⚠️ 封驳
> 轮次：第 {round} 轮
> 原因：{reason}

中书省正在修改方案...
```

#### 任务完成推送

```markdown
🎉 **任务完成**

> 标题：{title}
> 耗时：{duration}
> Token：{tokens}

**执行摘要**
{summary}

查看详情：/tasks {task_id}
```

### 4.3 推送配置

```yaml
# config.yaml
multi_agent:
  notifications:
    enabled: true
    # 推送渠道：origin（原对话）
    channel: "origin"
    # 推送级别：key（关键节点）
    level: "key"
    # 关键节点列表
    key_stages:
      - task_started
      - review_approved
      - review_rejected
      - dispatched
      - agent_completed
      - task_completed
      - task_failed
```

---

## 五、定期报告

### 5.1 每日报告 (09:30)

#### 飞书 Markdown

```markdown
📊 **多Agent日报** 
`2026-04-16`

---

**📈 今日数据**

| 指标 | 数值 |
|------|------|
| 新增任务 | 8 |
| 完成任务 | 12 |
| 进行中 | 3 |
| 失败 | 1 |
| 成功率 | 92% |
| Token消耗 | 45,230 |

---

**🔥 活跃 Agent**

| Agent | 调用 | Token |
|-------|------|-------|
| 工部 | 5 | 12,340 |
| 户部 | 3 | 8,560 |
| 礼部 | 2 | 6,780 |

---

**📋 进行中任务**
• task-abc1: API文档 (工部执行中)
• task-def2: 数据迁移 (户部执行中)
• task-xyz3: 报告撰写 (礼部执行中)

---

**❌ 失败任务**
• task-err1: 超时失败

`查看详情：/tasks active`
```

#### 微信纯文本

```
📊 多Agent日报 (2026-04-16)
━━━━━━━━━━━━━━━━━━━━━━━━━

【📈 今日数据】
新增：8 | 完成：12
进行中：3 | 失败：1
成功率：92%
Token：45,230

【🔥 活跃 Agent】
工部 5次 | 户部 3次 | 礼部 2次

【📋 进行中】
• task-abc1: API文档 (工部)
• task-def2: 数据迁移 (户部)

【❌ 失败】
• task-err1: 超时失败

━━━━━━━━━━━━━━━━━━━━━━━━━
/tasks active 查看详情
```

### 5.2 每周报告 (周一 09:30)

#### 飞书 Markdown

```markdown
📊 **多Agent周报**
`2026年4月第3周`

---

**📈 本周数据**

| 指标 | 数值 | 环比 |
|------|------|------|
| 新增任务 | 56 | ↑ 15% |
| 完成任务 | 52 | ↑ 12% |
| 成功率 | 93% | ↑ 3% |
| 总Token | 312,450 | ↓ 8% |
| 平均耗时 | 4.2分钟 | ↓ 5% |

---

**🏆 Agent 排行榜**

| 排名 | Agent | 调用 | Token | 成功率 |
|------|-------|------|-------|--------|
| 🥇 | 工部 | 23 | 62,340 | 96% |
| 🥈 | 户部 | 18 | 45,670 | 94% |
| 🥉 | 礼部 | 11 | 28,900 | 91% |

---

**📊 每日趋势**

```
周一 ████████ 8
周二 ██████████ 10
周三 ███████ 7
周四 ██████████████ 14
周五 ████████████ 12
周六 ███ 3
周末 ██ 2
```

---

**💡 系统建议**
• 工部负载最高，建议拆分复杂任务
• 成功率稳定在 90%+，系统运行良好
• Token 消耗下降，成本控制有效

`查看详情：/tasks stats`
```

### 5.3 定时配置

```yaml
# config.yaml
multi_agent:
  reports:
    daily:
      enabled: true
      time: "09:30"        # 每天 09:30
      channel: "origin"    # 推送到原对话
    weekly:
      enabled: true
      day: "monday"        # 每周一
      time: "09:30"
      channel: "origin"
```

---

## 六、实施计划

### 6.1 阶段划分

| 阶段 | 任务 | 工时 | 产出文件 |
|------|------|------|----------|
| **Phase 1** | 手动查询基础 | 2h | gateway/run.py, commands.py |
| **Phase 2** | 卡片格式适配 | 1h | multi_agent/dashboard_formatter.py |
| **Phase 3** | 扩展查询指令 | 1h | gateway/run.py |
| **Phase 4** | 关键节点推送 | 2h | orchestrator.py, gateway/run.py |
| **Phase 5** | 定期报告 | 2h | cron/jobs.py |

**总计：8h**

### 6.2 详细任务

#### Phase 1: 手动查询基础 (2h)

**任务列表**：
- [ ] 修改 `commands.py`，移除 `cli_only=True`
- [ ] 在 `gateway/run.py` 添加 `canonical == "tasks"` 处理
- [ ] 实现 `_handle_tasks_command()` 方法
- [ ] 实现 `_format_tasks_list()` 卡片格式化
- [ ] 实现平台检测（飞书/微信）
- [ ] 测试 `/tasks` 在飞书/微信可用

**产出**：
```
gateway/run.py          # 添加 _handle_tasks_command()
hermes_cli/commands.py  # 修改 tasks 命令定义
```

#### Phase 2: 卡片格式适配 (1h)

**任务列表**：
- [ ] 创建 `multi_agent/dashboard_formatter.py`
- [ ] 实现 `TaskCardFormatter` 类
- [ ] 实现飞书 Markdown 格式化
- [ ] 实现微信纯文本格式化
- [ ] 实现 `StatsCardFormatter` 类
- [ ] 实现 `TaskDetailFormatter` 类

**产出**：
```
multi_agent/dashboard_formatter.py  # 卡片格式化模块 (~500行)
```

#### Phase 3: 扩展查询指令 (1h)

**任务列表**：
- [ ] 实现 `/tasks stats` 统计面板
- [ ] 实现 `/tasks stats daily/weekly` 时间统计
- [ ] 实现 `/tasks stats agents` Agent 排行
- [ ] 实现 `/tasks active` 活跃任务
- [ ] 实现 `/tasks failed` 失败任务
- [ ] 实现 `/tasks <id> events` 事件流
- [ ] 实现 `/tasks <id> workspace` 工作空间

**产出**：
```
gateway/run.py  # 扩展 _handle_tasks_command()
```

#### Phase 4: 关键节点推送 (2h)

**任务列表**：
- [ ] 修改 `orchestrator.py` 的 `_notify_progress()`
- [ ] 添加推送判断逻辑（关键节点）
- [ ] 实现推送到原对话的机制
- [ ] 实现 `_send_notification()` 方法
- [ ] 配置 `multi_agent.notifications` 读取
- [ ] 测试各节点推送

**产出**：
```
multi_agent/orchestrator.py  # 推送逻辑
gateway/run.py              # 推送方法
```

#### Phase 5: 定期报告 (2h)

**任务列表**：
- [ ] 创建 `MultiAgentDailyReportJob` 类型
- [ ] 创建 `MultiAgentWeeklyReportJob` 类型
- [ ] 实现报告生成逻辑
- [ ] 实现定时任务注册
- [ ] 配置读取和验证
- [ ] 测试定时推送

**产出**：
```
cron/jobs.py                    # 新增 Job 类型
multi_agent/report_generator.py # 报告生成模块
```

---

## 七、配置项说明

### 7.1 完整配置

```yaml
# ~/.hermes/config.yaml

multi_agent:
  # 多Agent模式开关
  enabled: true
  mode: "three_provinces"
  
  # 任务通知配置
  notifications:
    enabled: true
    channel: "origin"          # origin（原对话）或 home（Home Channel）
    level: "key"               # all（所有节点）| key（关键节点）| none
    key_stages:
      - task_started           # 任务开始
      - review_approved        # 审议通过
      - review_rejected        # 审议封驳
      - dispatched             # 派发执行
      - agent_completed        # Agent完成
      - task_completed         # 任务完成
      - task_failed            # 任务失败
  
  # 定期报告配置
  reports:
    daily:
      enabled: true
      time: "09:30"            # 每天 09:30
      channel: "origin"
    weekly:
      enabled: true
      day: "monday"            # 每周一
      time: "09:30"
      channel: "origin"
  
  # 显示配置
  display:
    task_list_limit: 10        # 任务列表显示数量
    show_token_stats: true     # 显示 Token 统计
    show_duration: true        # 显示耗时
```

### 7.2 环境变量

```bash
# ~/.hermes/.env

# 多Agent通知（可选，配置文件优先）
MULTI_AGENT_NOTIFICATIONS_ENABLED=true
MULTI_AGENT_NOTIFICATIONS_CHANNEL=origin
MULTI_AGENT_REPORTS_DAILY_TIME=09:30
```

---

## 八、验收标准

### 8.1 功能验收

- [ ] `/tasks` 在飞书/微信返回卡片格式
- [ ] `/tasks stats` 显示统计面板
- [ ] `/tasks <id>` 显示任务详情
- [ ] `/tasks <id> events` 显示事件流
- [ ] `/tasks <id> audit` 显示审计日志
- [ ] `/tasks <id> workspace` 显示工作空间
- [ ] `/tasks active` 显示活跃任务
- [ ] `/tasks failed` 显示失败任务
- [ ] 关键节点推送到原对话
- [ ] 每日 09:30 自动推送日报
- [ ] 每周一 09:30 自动推送周报

### 8.2 格式验收

- [ ] 飞书消息支持 Markdown 表格
- [ ] 微信消息纯文本可读
- [ ] 卡片格式整齐美观
- [ ] 状态图标正确显示

### 8.3 性能验收

- [ ] `/tasks` 响应时间 < 1s
- [ ] 报告生成时间 < 2s
- [ ] 不影响正常任务执行

---

## 九、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 微信消息长度超限 | 中 | 显示截断 | 分段发送，控制单条 < 4000 字符 |
| 推送频率过高 | 低 | 用户打扰 | 仅推送关键节点，支持关闭 |
| 定时任务冲突 | 低 | 报告丢失 | 使用 Cron 内置重试机制 |
| 格式兼容问题 | 低 | 显示异常 | 降级到纯文本格式 |

---

## 十、后续扩展

完成本方案后，可继续扩展：

1. **任务干预**：`/tasks <id> cancel` 取消任务
2. **任务重试**：`/tasks <id> retry` 重试失败任务
3. **自定义报告**：用户自定义报告时间/内容
4. **多维度统计**：按项目/标签/时间范围统计
5. **趋势图表**：发送统计图表图片

---

**文档版本**: v1.0  
**创建时间**: 2026-04-16  
**预计完成**: 8 工时
