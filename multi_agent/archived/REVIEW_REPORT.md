# 三省六部多Agent系统 - 实施审查报告

> **更新**: 2026-04-16  
> **状态**: ✅ P0问题已修复，P1待实施

## 一、架构概览

### 当前实现的组件

| 组件 | 文件 | 状态 | 说明 |
|------|------|------|------|
| Agent定义 | multi_agent/agents/*.yaml | ✅ 完整 | 11个Agent定义完整 |
| Agent加载 | agent_loader.py | ✅ 完整 | 正确加载YAML配置 |
| Agent池 | agent_pool.py | ✅ 完整 | LLM调用+Agent间调用 |
| 调度器 | orchestrator.py | ✅ 完整 | 主流程+审议封驳 |
| CLI集成 | cli.py | ✅ 完整 | /mode命令和消息路由 |
| 状态持久化 | - | ❌ 缺失 | 任务仅存内存 (P1-1) |
| 事件总线 | - | ❌ 缺失 | 无异步消息机制 (P2) |

---

## 二、关键问题分析（已更新）

### 问题1：Agent间调用 ✅ 已修复

**原始问题**：
- YAML中定义了 `can_call` 字段，如尚书省可调用六部
- 但 `agent_pool.execute()` 实际上不处理Agent间调用
- 尚书省只能自己执行任务，无法真正派发给六部

**修复内容**：
- 添加 `dispatch_to_agent()` 方法支持Agent间调用
- 添加 `dispatch_parallel()` 方法支持并行派发
- 重写 `_execute_plan()` 让尚书省真正派发给六部

---

### 问题2：审议封驳逻辑 ✅ 已修复

**原始问题**：
- 门下省可以返回 `rejected`，但代码中标注了 `# TODO: 实现方案修改逻辑`
- 审议循环只计数轮数，不处理修改方案

**修复内容**：
- 在 `_review_plan()` 中处理 rejected 情况
- 新增 `_revise_plan()` 方法调用中书省修改方案
- 将审议意见传递给中书省作为修改依据

---

### 问题3：同步调用阻塞 🟡 中等

**现状**：
- 整个流程是同步调用：太子→中书→门下→尚书
- 每个Agent等待上一个完成后才能开始
- 无并行执行能力

**影响**：
- 响应时间长（多个LLM调用串行）
- 无法利用并行处理优化性能

---

### 问题4：任务状态不可见 🟡 中等

**现状**：
- 任务状态只存在于内存
- 用户看不到当前执行到哪一步
- 无法恢复中断的任务

**影响**：
- 用户体验差，不知道任务进度
- 出错后无法从断点恢复
- 无法查看历史任务

---

### 问题5：输出解析脆弱 🟡 中等

**现状**：
- 依赖LLM输出JSON格式
- 虽然有容错解析（正则提取），但可能丢失信息
- 某些模型的输出可能完全无法解析

**影响**：
- 分类错误（闲聊当旨意）
- 规划内容丢失
- 执行结果不完整

---

### 问题6：工具权限控制不精确 🟢 轻微

**现状**：
- `tools_allowed` 定义了工具列表
- `_resolve_toolsets()` 只做简单映射
- 部分工具名可能无法正确映射到工具集

---

## 三、与原始Edict设计对比

| 特性 | Edict设计 | 当前实现 | 差距 |
|------|-----------|----------|------|
| Agent层级 | 3层（入口/中枢/执行） | ✅ 一致 | 无 |
| Agent间调用 | 支持 | ❌ 未实现 | 大 |
| 审议封驳 | 完整循环 | ❌ TODO | 大 |
| 异步消息 | Redis Streams | ❌ 无 | 中 |
| 状态存储 | SQLite/Redis | ❌ 内存 | 中 |
| 配置驱动 | YAML完整 | ✅ 一致 | 无 |
| 工具权限 | 精确控制 | ⚠️ 近似 | 小 |

---

## 四、修复优先级

### P0 - 必须修复（核心功能）✅ 已完成

1. **实现Agent间调用** ✅
   - 尚书省调用六部
   - 中书省调用户部/兵部/礼部获取信息
   - 支持串行和并行派发

2. **实现审议封驳逻辑** ✅
   - 门下省封驳后，将意见返回中书省
   - 中书省根据意见修改方案
   - 重新提交审议

### P1 - 应该修复（用户体验）⏳ 待实施

3. **任务状态持久化**
   - SQLite存储任务状态
   - 支持任务恢复
   - 支持历史查询

4. **任务进度反馈**
   - 显示当前执行阶段
   - 显示正在执行的Agent
   - 估算剩余时间

### P2 - 可以优化（性能/健壮性）

5. **异步执行支持**
   - 引入事件总线
   - 支持并行任务
   - 非阻塞执行

6. **输出解析增强**
   - 使用 structured output
   - 更健壮的容错机制
   - 输出验证

---

## 五、修复方案

### 方案1：Agent间调用（推荐）

在 `agent_pool.py` 中增加 `_dispatch_to_agent()` 方法：

```python
def dispatch_to_agent(
    self,
    from_agent: str,
    to_agent: str,
    task: str,
    context: Dict[str, Any] = None,
) -> str:
    """Agent间调用"""
    # 1. 检查调用权限
    if not self.can_call(from_agent, to_agent):
        return json.dumps({"error": f"{from_agent} 无权调用 {to_agent}"})
    
    # 2. 创建子任务
    subtask_id = f"{from_agent}-{to_agent}-{uuid.uuid4().hex[:6]}"
    
    # 3. 执行目标Agent
    return self.execute(
        agent_id=to_agent,
        task_id=subtask_id,
        input_data=task,
        context=context,
    )
```

修改尚书省的 prompt，明确要求调用六部而非自己执行。

### 方案2：审议封驳逻辑

在 `orchestrator.py` 中修改 `_review_plan()`：

```python
def _review_plan(self, task: TaskContext) -> Dict[str, Any]:
    for round_num in range(1, max_rounds + 1):
        review = self._call_menxia(task.plan)
        
        if review["decision"] == "approved":
            return review
        
        if review["decision"] == "rejected":
            # 将审议意见返回中书省修改方案
            task.plan = self._revise_plan(task.plan, review)
            continue
    
    # 最后一轮强制通过
    return {"decision": "approved"}

def _revise_plan(self, plan: Dict, review: Dict) -> Dict:
    """根据审议意见修改方案"""
    return agent_pool.execute(
        agent_id="zhongshu",
        input_data=json.dumps({
            "original_plan": plan,
            "review_feedback": review,
        }),
        context={"action": "revise"},
    )
```

---

## 六、实施计划

| 阶段 | 任务 | 预计工时 | 状态 |
|------|------|----------|------|
| Phase 1 | 框架搭建 | 4h | ✅ 完成 |
| Phase 2 | LLM调用集成 | 2h | ✅ 完成 |
| Phase 3 | Agent间调用 | 3h | ✅ 完成 |
| Phase 4 | 审议封驳逻辑 | 2h | ✅ 完成 |
| Phase 5 | 状态持久化 | 2h | ⏳ 待开始 |
| Phase 6 | 进度反馈 | 1h | ⏳ 待开始 |

**已完成：11h，剩余：3h**

---

## 七、结论

### 当前状态

✅ **Phase 1-2 完成** - 框架搭建 + LLM调用集成  
✅ **P0 问题修复完成** - Agent间调用 + 审议封驳逻辑  

### 系统功能

当前系统已具备完整的三省六部流程：

1. **太子分类** - 闲聊/旨意分类
2. **中书省规划** - 任务分析与方案制定
3. **门下省审议** - 审议循环（最多3轮）+ 封驳修改
4. **尚书省派发** - 派发决策 + 调用六部
5. **六部执行** - 专业分工执行
6. **汇总报告** - 结果聚合返回

### 待完成工作

- P1-1: SQLite 状态持久化（3h）
- P1-2: 任务进度反馈（2h）

**建议**：优先完成状态持久化，这是任务恢复和历史查询的基础。
