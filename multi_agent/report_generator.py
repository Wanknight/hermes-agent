"""
多Agent定期报告生成器

支持日报和周报，根据平台类型（飞书/微信）生成不同格式的报告。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# 导入时间工具
try:
    from hermes_time import now as _hermes_now
except ImportError:
    from datetime import datetime as _dt
    def _hermes_now():
        return _dt.now()


# =============================================================================
# 日报生成
# =============================================================================

def generate_daily_report(
    stats: Dict[str, Any],
    active_tasks: List[Dict[str, Any]],
    failed_tasks: List[Dict[str, Any]],
    agent_stats: List[Dict[str, Any]],
    platform: str = "feishu",
) -> str:
    """
    生成日报
    
    Args:
        stats: 今日统计数据
        active_tasks: 进行中的任务列表
        failed_tasks: 失败的任务列表
        agent_stats: Agent 统计数据
        platform: 平台类型 ("feishu" 或 "weixin")
    
    Returns:
        格式化的报告字符串
    """
    today = _hermes_now().strftime("%Y-%m-%d")
    
    if platform == "feishu":
        return _format_daily_report_feishu(today, stats, active_tasks, failed_tasks, agent_stats)
    else:
        return _format_daily_report_weixin(today, stats, active_tasks, failed_tasks, agent_stats)


def _format_daily_report_feishu(
    date: str,
    stats: Dict[str, Any],
    active_tasks: List[Dict[str, Any]],
    failed_tasks: List[Dict[str, Any]],
    agent_stats: List[Dict[str, Any]],
) -> str:
    """飞书 Markdown 格式日报"""
    
    lines = []
    lines.append(f"📊 **多Agent日报**")
    lines.append(f"`{date}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**📈 今日数据**")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 新增任务 | {stats.get('new_tasks', 0)} |")
    lines.append(f"| 完成任务 | {stats.get('completed_tasks', 0)} |")
    lines.append(f"| 进行中 | {stats.get('active_tasks', 0)} |")
    lines.append(f"| 失败 | {stats.get('failed_tasks', 0)} |")
    lines.append(f"| 成功率 | {stats.get('success_rate', 0):.0%} |")
    lines.append(f"| Token消耗 | {stats.get('total_tokens', 0):,} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 活跃 Agent
    if agent_stats:
        lines.append("**🔥 活跃 Agent**")
        lines.append("")
        lines.append("| Agent | 调用 | Token |")
        lines.append("|-------|------|-------|")
        for agent in agent_stats[:5]:  # 最多显示 5 个
            name = agent.get("name", "?")
            calls = agent.get("calls", 0)
            tokens = agent.get("tokens", 0)
            lines.append(f"| {name} | {calls} | {tokens:,} |")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # 进行中任务
    if active_tasks:
        lines.append("**📋 进行中任务**")
        for task in active_tasks[:5]:  # 最多显示 5 个
            task_id = task.get("task_id", "?")[:8]
            title = task.get("title", "无标题")[:20]
            agent = task.get("current_agent", "?")
            lines.append(f"• {task_id}: {title} ({agent}执行中)")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # 失败任务
    if failed_tasks:
        lines.append("**❌ 失败任务**")
        for task in failed_tasks[:5]:  # 最多显示 5 个
            task_id = task.get("task_id", "?")[:8]
            error = task.get("error", "未知错误")[:30]
            lines.append(f"• {task_id}: {error}")
        lines.append("")
    
    lines.append("`查看详情：/tasks active`")
    
    return "\n".join(lines)


def _format_daily_report_weixin(
    date: str,
    stats: Dict[str, Any],
    active_tasks: List[Dict[str, Any]],
    failed_tasks: List[Dict[str, Any]],
    agent_stats: List[Dict[str, Any]],
) -> str:
    """微信纯文本格式日报"""
    
    lines = []
    lines.append(f"📊 多Agent日报 ({date})")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("【📈 今日数据】")
    lines.append(f"新增：{stats.get('new_tasks', 0)} | 完成：{stats.get('completed_tasks', 0)}")
    lines.append(f"进行中：{stats.get('active_tasks', 0)} | 失败：{stats.get('failed_tasks', 0)}")
    lines.append(f"成功率：{stats.get('success_rate', 0):.0%}")
    lines.append(f"Token：{stats.get('total_tokens', 0):,}")
    lines.append("")
    
    # 活跃 Agent
    if agent_stats:
        lines.append("【🔥 活跃 Agent】")
        agent_parts = []
        for agent in agent_stats[:3]:
            name = agent.get("name", "?")
            calls = agent.get("calls", 0)
            agent_parts.append(f"{name} {calls}次")
        lines.append(" | ".join(agent_parts))
        lines.append("")
    
    # 进行中任务
    if active_tasks:
        lines.append("【📋 进行中】")
        for task in active_tasks[:3]:
            task_id = task.get("task_id", "?")[:8]
            title = task.get("title", "无标题")[:15]
            agent = task.get("current_agent", "?")
            lines.append(f"• {task_id}: {title} ({agent})")
        lines.append("")
    
    # 失败任务
    if failed_tasks:
        lines.append("【❌ 失败】")
        for task in failed_tasks[:3]:
            task_id = task.get("task_id", "?")[:8]
            error = task.get("error", "未知错误")[:20]
            lines.append(f"• {task_id}: {error}")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("/tasks active 查看详情")
    
    return "\n".join(lines)


# =============================================================================
# 周报生成
# =============================================================================

def generate_weekly_report(
    stats: Dict[str, Any],
    daily_trend: List[Dict[str, Any]],
    agent_ranking: List[Dict[str, Any]],
    suggestions: List[str],
    platform: str = "feishu",
) -> str:
    """
    生成周报
    
    Args:
        stats: 本周统计数据
        daily_trend: 每日趋势数据
        agent_ranking: Agent 排行榜
        suggestions: 系统建议列表
        platform: 平台类型 ("feishu" 或 "weixin")
    
    Returns:
        格式化的报告字符串
    """
    now = _hermes_now()
    # 计算周数
    week_num = (now.day - 1) // 7 + 1
    week_str = f"{now.year}年{now.month}月第{week_num}周"
    
    if platform == "feishu":
        return _format_weekly_report_feishu(week_str, stats, daily_trend, agent_ranking, suggestions)
    else:
        return _format_weekly_report_weixin(week_str, stats, daily_trend, agent_ranking, suggestions)


def _format_weekly_report_feishu(
    week_str: str,
    stats: Dict[str, Any],
    daily_trend: List[Dict[str, Any]],
    agent_ranking: List[Dict[str, Any]],
    suggestions: List[str],
) -> str:
    """飞书 Markdown 格式周报"""
    
    lines = []
    lines.append(f"📊 **多Agent周报**")
    lines.append(f"`{week_str}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**📈 本周数据**")
    lines.append("")
    lines.append("| 指标 | 数值 | 环比 |")
    lines.append("|------|------|------|")
    lines.append(f"| 新增任务 | {stats.get('new_tasks', 0)} | {stats.get('new_tasks_trend', '-')} |")
    lines.append(f"| 完成任务 | {stats.get('completed_tasks', 0)} | {stats.get('completed_tasks_trend', '-')} |")
    lines.append(f"| 成功率 | {stats.get('success_rate', 0):.0%} | {stats.get('success_rate_trend', '-')} |")
    lines.append(f"| 总Token | {stats.get('total_tokens', 0):,} | {stats.get('total_tokens_trend', '-')} |")
    lines.append(f"| 平均耗时 | {stats.get('avg_duration', 0):.1f}分钟 | {stats.get('avg_duration_trend', '-')} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Agent 排行榜
    if agent_ranking:
        lines.append("**🏆 Agent 排行榜**")
        lines.append("")
        lines.append("| 排名 | Agent | 调用 | Token | 成功率 |")
        lines.append("|------|-------|------|-------|--------|")
        medals = ["🥇", "🥈", "🥉"]
        for i, agent in enumerate(agent_ranking[:5]):
            medal = medals[i] if i < 3 else f"#{i+1}"
            name = agent.get("name", "?")
            calls = agent.get("calls", 0)
            tokens = agent.get("tokens", 0)
            rate = agent.get("success_rate", 0)
            lines.append(f"| {medal} | {name} | {calls} | {tokens:,} | {rate:.0%} |")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # 每日趋势
    if daily_trend:
        lines.append("**📊 每日趋势**")
        lines.append("")
        lines.append("```")
        for day in daily_trend:
            weekday = day.get("weekday", "?")
            count = day.get("count", 0)
            bar = "█" * min(count, 20)
            lines.append(f"{weekday} {bar} {count}")
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # 系统建议
    if suggestions:
        lines.append("**💡 系统建议**")
        for suggestion in suggestions[:3]:
            lines.append(f"• {suggestion}")
        lines.append("")
    
    lines.append("`查看详情：/tasks stats`")
    
    return "\n".join(lines)


def _format_weekly_report_weixin(
    week_str: str,
    stats: Dict[str, Any],
    daily_trend: List[Dict[str, Any]],
    agent_ranking: List[Dict[str, Any]],
    suggestions: List[str],
) -> str:
    """微信纯文本格式周报"""
    
    lines = []
    lines.append(f"📊 多Agent周报 ({week_str})")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("【📈 本周数据】")
    lines.append(f"新增：{stats.get('new_tasks', 0)} | 完成：{stats.get('completed_tasks', 0)}")
    lines.append(f"成功率：{stats.get('success_rate', 0):.0%}")
    lines.append(f"Token：{stats.get('total_tokens', 0):,}")
    lines.append(f"平均耗时：{stats.get('avg_duration', 0):.1f}分钟")
    lines.append("")
    
    # Agent 排行榜
    if agent_ranking:
        lines.append("【🏆 Agent排行】")
        for i, agent in enumerate(agent_ranking[:3]):
            name = agent.get("name", "?")
            calls = agent.get("calls", 0)
            rate = agent.get("success_rate", 0)
            lines.append(f"{i+1}. {name}: {calls}次, {rate:.0%}成功率")
        lines.append("")
    
    # 每日趋势（简化版）
    if daily_trend:
        lines.append("【📊 每日趋势】")
        trend_parts = []
        for day in daily_trend[:7]:
            weekday = day.get("weekday", "?")[:2]
            count = day.get("count", 0)
            trend_parts.append(f"{weekday}:{count}")
        lines.append(" | ".join(trend_parts))
        lines.append("")
    
    # 系统建议
    if suggestions:
        lines.append("【💡 建议】")
        for suggestion in suggestions[:2]:
            lines.append(f"• {suggestion[:30]}")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("/tasks stats 查看详情")
    
    return "\n".join(lines)


# =============================================================================
# 数据收集
# =============================================================================

def collect_daily_stats(orchestrator) -> Dict[str, Any]:
    """
    收集今日统计数据
    
    Args:
        orchestrator: MultiAgentOrchestrator 实例
    
    Returns:
        统计数据字典
    """
    from multi_agent import TaskStatus
    
    now = _hermes_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 获取所有任务
    all_tasks = orchestrator.list_tasks(limit=1000)
    
    # 筛选今日任务
    today_tasks = []
    for task in all_tasks:
        created_at = task.created_at
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                continue
        if created_at and created_at >= today_start:
            today_tasks.append(task)
    
    # 统计
    new_tasks = len(today_tasks)
    completed_tasks = len([t for t in today_tasks if t.status == TaskStatus.COMPLETED])
    failed_tasks = len([t for t in today_tasks if t.status == TaskStatus.FAILED])
    active_tasks = len([t for t in today_tasks if t.status in (
        TaskStatus.CLASSIFYING,
        TaskStatus.PLANNING,
        TaskStatus.REVIEWING,
        TaskStatus.EXECUTING,
    )])
    
    # 成功率
    finished_tasks = completed_tasks + failed_tasks
    success_rate = completed_tasks / finished_tasks if finished_tasks > 0 else 1.0
    
    # Token 消耗
    total_tokens = sum(t.total_tokens or 0 for t in today_tasks)
    
    return {
        "new_tasks": new_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "active_tasks": active_tasks,
        "success_rate": success_rate,
        "total_tokens": total_tokens,
    }


def collect_weekly_stats(orchestrator) -> Dict[str, Any]:
    """
    收集本周统计数据
    
    Args:
        orchestrator: MultiAgentOrchestrator 实例
    
    Returns:
        统计数据字典
    """
    from multi_agent import TaskStatus
    
    now = _hermes_now()
    # 计算本周开始（周一）
    days_since_monday = now.weekday()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
    
    # 获取所有任务
    all_tasks = orchestrator.list_tasks(limit=1000)
    
    # 筛选本周任务
    week_tasks = []
    for task in all_tasks:
        created_at = task.created_at
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                continue
        if created_at and created_at >= week_start:
            week_tasks.append(task)
    
    # 统计
    new_tasks = len(week_tasks)
    completed_tasks = len([t for t in week_tasks if t.status == TaskStatus.COMPLETED])
    failed_tasks = len([t for t in week_tasks if t.status == TaskStatus.FAILED])
    
    # 成功率
    finished_tasks = completed_tasks + failed_tasks
    success_rate = completed_tasks / finished_tasks if finished_tasks > 0 else 1.0
    
    # Token 消耗
    total_tokens = sum(t.total_tokens or 0 for t in week_tasks)
    
    # 平均耗时
    durations = []
    for t in week_tasks:
        if t.status == TaskStatus.COMPLETED and t.started_at and t.completed_at:
            try:
                if isinstance(t.started_at, str):
                    started = datetime.fromisoformat(t.started_at)
                else:
                    started = t.started_at
                if isinstance(t.completed_at, str):
                    completed = datetime.fromisoformat(t.completed_at)
                else:
                    completed = t.completed_at
                durations.append((completed - started).total_seconds() / 60)
            except Exception:
                pass
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return {
        "new_tasks": new_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "success_rate": success_rate,
        "total_tokens": total_tokens,
        "avg_duration": avg_duration,
    }


def collect_daily_trend(orchestrator) -> List[Dict[str, Any]]:
    """
    收集每日趋势数据
    
    Returns:
        每日任务数量列表
    """
    from multi_agent import TaskStatus
    
    now = _hermes_now()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    # 计算本周开始（周一）
    days_since_monday = now.weekday()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
    
    # 获取所有任务
    all_tasks = orchestrator.list_tasks(limit=1000)
    
    # 按天统计
    daily_counts = []
    for i in range(7):
        day_start = week_start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        count = 0
        for task in all_tasks:
            created_at = task.created_at
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    continue
            if created_at and day_start <= created_at < day_end:
                count += 1
        
        daily_counts.append({
            "weekday": weekday_names[i],
            "count": count,
        })
    
    return daily_counts


def collect_agent_ranking(orchestrator) -> List[Dict[str, Any]]:
    """
    收集 Agent 排行榜数据
    
    Returns:
        Agent 统计列表，按调用次数排序
    """
    from multi_agent import TaskStatus
    
    now = _hermes_now()
    # 计算本周开始（周一）
    days_since_monday = now.weekday()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
    
    # 获取所有任务
    all_tasks = orchestrator.list_tasks(limit=1000)
    
    # 筛选本周任务
    week_tasks = []
    for task in all_tasks:
        created_at = task.created_at
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                continue
        if created_at and created_at >= week_start:
            week_tasks.append(task)
    
    # 统计 Agent 调用
    agent_stats = {}
    for task in week_tasks:
        # 从事件中获取调用的 Agent
        events = task.events or []
        for event in events:
            agent_name = event.get("agent")
            if agent_name:
                if agent_name not in agent_stats:
                    agent_stats[agent_name] = {
                        "name": agent_name,
                        "calls": 0,
                        "tokens": 0,
                        "success": 0,
                        "total": 0,
                    }
                agent_stats[agent_name]["calls"] += 1
                agent_stats[agent_name]["tokens"] += event.get("tokens", 0)
                if event.get("success"):
                    agent_stats[agent_name]["success"] += 1
                agent_stats[agent_name]["total"] += 1
    
    # 计算成功率并排序
    result = []
    for name, stats in agent_stats.items():
        stats["success_rate"] = stats["success"] / stats["total"] if stats["total"] > 0 else 1.0
        result.append(stats)
    
    result.sort(key=lambda x: x["calls"], reverse=True)
    return result


def generate_suggestions(stats: Dict[str, Any], agent_ranking: List[Dict[str, Any]]) -> List[str]:
    """
    生成系统建议
    
    Args:
        stats: 本周统计数据
        agent_ranking: Agent 排行榜
    
    Returns:
        建议列表
    """
    suggestions = []
    
    # 根据成功率给出建议
    if stats.get("success_rate", 1.0) < 0.8:
        suggestions.append("成功率较低，建议检查失败任务的错误日志")
    elif stats.get("success_rate", 1.0) >= 0.9:
        suggestions.append("成功率稳定在 90%+，系统运行良好")
    
    # 根据 Agent 负载给出建议
    if agent_ranking:
        top_agent = agent_ranking[0]
        total_calls = sum(a["calls"] for a in agent_ranking)
        if total_calls > 0 and top_agent["calls"] / total_calls > 0.5:
            suggestions.append(f"{top_agent['name']}负载最高（{top_agent['calls']/total_calls:.0%}），建议拆分复杂任务")
    
    # 根据 Token 消耗给出建议
    if stats.get("total_tokens", 0) > 100000:
        suggestions.append("Token 消耗较高，考虑优化提示词或使用更高效的模型")
    
    return suggestions if suggestions else ["系统运行正常，无特别建议"]


# =============================================================================
# 辅助函数：为脚本提供数据收集接口
# =============================================================================

def get_active_tasks(orchestrator) -> List[Dict[str, Any]]:
    """
    获取正在执行的任务列表
    
    Args:
        orchestrator: MultiAgentOrchestrator 实例
    
    Returns:
        任务列表，每个任务包含 task_id, title, current_agent
    """
    from multi_agent import TaskStatus
    
    all_tasks = orchestrator.list_tasks(limit=100)
    
    active_statuses = (
        TaskStatus.CLASSIFYING,
        TaskStatus.PLANNING,
        TaskStatus.REVIEWING,
        TaskStatus.EXECUTING,
    )
    
    result = []
    for task in all_tasks:
        if task.status in active_statuses:
            result.append({
                "task_id": task.task_id,
                "title": task.title or "无标题",
                "current_agent": task.current_agent or "?",
            })
    
    return result


def get_failed_tasks_today(orchestrator) -> List[Dict[str, Any]]:
    """
    获取今日失败的任务列表
    
    Args:
        orchestrator: MultiAgentOrchestrator 实例
    
    Returns:
        任务列表，每个任务包含 task_id, error
    """
    from multi_agent import TaskStatus
    
    now = _hermes_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    all_tasks = orchestrator.list_tasks(limit=100)
    
    result = []
    for task in all_tasks:
        if task.status != TaskStatus.FAILED:
            continue
        
        # 检查是否今日创建
        created_at = task.created_at
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                continue
        
        if created_at and created_at >= today_start:
            result.append({
                "task_id": task.task_id,
                "error": task.error or "未知错误",
            })
    
    return result


def get_agent_stats_today(orchestrator) -> List[Dict[str, Any]]:
    """
    获取今日 Agent 调用统计
    
    Args:
        orchestrator: MultiAgentOrchestrator 实例
    
    Returns:
        Agent 统计列表
    """
    # 简化实现：从状态管理器获取统计
    try:
        state_manager = orchestrator._get_state_manager()
        today_stats = state_manager.get_agent_stats_today()
        
        # 转换为列表格式
        result = []
        for agent_id, stats in today_stats.items():
            result.append({
                "name": stats.get("name", agent_id),
                "calls": stats.get("calls", 0),
                "tokens": stats.get("tokens", 0),
            })
        
        # 按调用次数排序
        result.sort(key=lambda x: x["calls"], reverse=True)
        return result
        
    except Exception:
        # 降级：返回空列表
        return []
