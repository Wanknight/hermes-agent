"""
Dashboard Formatter - 多Agent任务查询卡片格式化

为飞书和微信平台提供不同格式的任务查询结果展示。
"""

from typing import Optional
from multi_agent import TaskStatus


# 状态图标映射
STATUS_ICONS = {
    TaskStatus.CREATED: "⏳",
    TaskStatus.CLASSIFYING: "📥",
    TaskStatus.PLANNING: "📝",
    TaskStatus.REVIEWING: "🔍",
    TaskStatus.DISPATCHING: "📤",
    TaskStatus.EXECUTING: "🔄",
    TaskStatus.COMPLETED: "✅",
    TaskStatus.FAILED: "❌",
}

# 状态中文映射
STATUS_CN = {
    TaskStatus.CREATED: "已创建",
    TaskStatus.CLASSIFYING: "分类中",
    TaskStatus.PLANNING: "规划中",
    TaskStatus.REVIEWING: "审核中",
    TaskStatus.DISPATCHING: "分发中",
    TaskStatus.EXECUTING: "执行中",
    TaskStatus.COMPLETED: "已完成",
    TaskStatus.FAILED: "失败",
}


def format_task_list(tasks: list, platform: str = "feishu") -> str:
    """
    格式化任务列表
    
    Args:
        tasks: 任务列表
        platform: 平台类型 "feishu" 或 "weixin"
    
    Returns:
        格式化后的字符串
    """
    if not tasks:
        return "暂无任务记录"
    
    if platform == "feishu":
        return _format_task_list_feishu(tasks)
    else:
        return _format_task_list_weixin(tasks)


def _format_task_list_feishu(tasks: list) -> str:
    """飞书格式 - 支持 Markdown"""
    lines = [
        "**📋 最近任务**",
        f"共 {len(tasks)} 条记录",
        "",
    ]
    
    for task in tasks:
        task_id = task.task_id[:8] + "..."
        status_icon = STATUS_ICONS.get(task.status, "⏳")
        status_cn = STATUS_CN.get(task.status, task.status.value)
        title = (task.title or "无标题")[:30]
        
        lines.append(f"{status_icon} **{task_id}** `{status_cn}` {title}")
    
    lines.extend([
        "",
        "_用法: /tasks [stats|<任务ID>]_",
    ])
    
    return "\n".join(lines)


def _format_task_list_weixin(tasks: list) -> str:
    """微信格式 - 纯文本，无 Markdown"""
    lines = [
        "【最近任务】",
        f"共 {len(tasks)} 条记录",
        "",
    ]
    
    for task in tasks:
        task_id = task.task_id[:8]
        status_icon = STATUS_ICONS.get(task.status, "⏳")
        status_cn = STATUS_CN.get(task.status, task.status.value)
        title = (task.title or "无标题")[:25]
        
        lines.append(f"{status_icon} {task_id} [{status_cn}] {title}")
    
    lines.extend([
        "",
        "用法: /tasks [stats|<任务ID>]",
    ])
    
    return "\n".join(lines)


def format_task_detail(task, platform: str = "feishu") -> str:
    """
    格式化单个任务详情
    
    Args:
        task: 任务对象
        platform: 平台类型
    
    Returns:
        格式化后的字符串
    """
    if platform == "feishu":
        return _format_task_detail_feishu(task)
    else:
        return _format_task_detail_weixin(task)


def _format_task_detail_feishu(task) -> str:
    """飞书格式 - 任务详情"""
    status_icon = STATUS_ICONS.get(task.status, "⏳")
    status_cn = STATUS_CN.get(task.status, task.status.value)
    
    lines = [
        f"**📋 任务: {task.title or task.task_id[:8]}**",
        "",
        f"**状态:** {status_icon} `{status_cn}`",
        f"**类型:** `{task.message_type.value}`",
        f"**创建时间:** {task.created_at}",
        "",
    ]
    
    # 进度历史
    if task.progress_history:
        lines.append("**进度历史:**")
        for p in task.progress_history[-5:]:
            agent = p.get('agent', '')
            stage = p.get('stage', '')
            msg = p.get('message', '')
            lines.append(f"  - [{stage}] {agent}: {msg}")
        lines.append("")
    
    lines.append("_使用 /tasks {task_id} audit 查看审计日志_")
    
    return "\n".join(lines)


def _format_task_detail_weixin(task) -> str:
    """微信格式 - 任务详情"""
    status_icon = STATUS_ICONS.get(task.status, "⏳")
    status_cn = STATUS_CN.get(task.status, task.status.value)
    
    lines = [
        f"【任务详情】{task.title or task.task_id[:8]}",
        "",
        f"状态: {status_icon} {status_cn}",
        f"类型: {task.message_type.value}",
        f"创建: {task.created_at}",
        "",
    ]
    
    # 进度历史
    if task.progress_history:
        lines.append("进度历史:")
        for p in task.progress_history[-5:]:
            agent = p.get('agent', '')
            stage = p.get('stage', '')
            msg = p.get('message', '')
            lines.append(f"  [{stage}] {agent}: {msg}")
        lines.append("")
    
    lines.append(f"查看审计: /tasks {task.task_id[:8]} audit")
    
    return "\n".join(lines)


def format_statistics(stats: dict, platform: str = "feishu") -> str:
    """
    格式化统计数据
    
    Args:
        stats: 统计数据字典
        platform: 平台类型
    
    Returns:
        格式化后的字符串
    """
    if platform == "feishu":
        return _format_statistics_feishu(stats)
    else:
        return _format_statistics_weixin(stats)


def _format_statistics_feishu(stats: dict) -> str:
    """飞书格式 - 统计数据"""
    lines = [
        "**📊 多Agent任务统计**",
        "",
        f"- **总任务数:** {stats.get('total_tasks', 0)}",
        f"- **已完成:** {stats.get('completed_tasks', 0)}",
        f"- **进行中:** {stats.get('active_tasks', 0)}",
        f"- **失败:** {stats.get('failed_tasks', 0)}",
    ]
    
    return "\n".join(lines)


def _format_statistics_weixin(stats: dict) -> str:
    """微信格式 - 统计数据"""
    lines = [
        "【任务统计】",
        "",
        f"总任务: {stats.get('total_tasks', 0)}",
        f"已完成: {stats.get('completed_tasks', 0)}",
        f"进行中: {stats.get('active_tasks', 0)}",
        f"失败: {stats.get('failed_tasks', 0)}",
    ]
    
    return "\n".join(lines)


def format_audit_logs(logs: list, task_id: str, platform: str = "feishu") -> str:
    """
    格式化审计日志
    
    Args:
        logs: 审计日志列表
        task_id: 任务ID
        platform: 平台类型
    
    Returns:
        格式化后的字符串
    """
    if not logs:
        return f"未找到任务的审计日志: {task_id}"
    
    if platform == "feishu":
        return _format_audit_logs_feishu(logs, task_id)
    else:
        return _format_audit_logs_weixin(logs, task_id)


def _format_audit_logs_feishu(logs: list, task_id: str) -> str:
    """飞书格式 - 审计日志"""
    lines = [
        f"**📜 审计日志 - {task_id}**",
        f"共 {len(logs)} 条记录",
        "",
    ]
    
    for log in logs:
        status_icon = "✅" if log.status == "success" else "❌" if log.status == "failed" else "⏳"
        time_str = log.created_at[11:19] if len(log.created_at) >= 19 else log.created_at
        agent_name = log.agent_name or log.agent_id
        latency_str = f"{log.latency_ms}ms" if log.latency_ms else "-"
        tokens_str = f"{log.tokens_used}t" if log.tokens_used else "-"
        
        lines.append(f"{status_icon} `{time_str}` **{agent_name}** {log.action} `{latency_str}` `{tokens_str}`")
        
        if log.error_message:
            error_preview = log.error_message[:50]
            if len(log.error_message) > 50:
                error_preview += "..."
            lines.append(f"   ⚠️ {error_preview}")
    
    lines.extend([
        "",
        "_延迟单位: ms, Token单位: 个_",
    ])
    
    return "\n".join(lines)


def _format_audit_logs_weixin(logs: list, task_id: str) -> str:
    """微信格式 - 审计日志"""
    lines = [
        f"【审计日志】{task_id}",
        f"共 {len(logs)} 条记录",
        "",
    ]
    
    for log in logs:
        status_icon = "✓" if log.status == "success" else "✗" if log.status == "failed" else "·"
        time_str = log.created_at[11:19] if len(log.created_at) >= 19 else log.created_at
        agent_name = log.agent_name or log.agent_id
        latency_str = f"{log.latency_ms}ms" if log.latency_ms else "-"
        
        lines.append(f"{status_icon} [{time_str}] {agent_name} {log.action} {latency_str}")
        
        if log.error_message:
            error_preview = log.error_message[:40]
            if len(log.error_message) > 40:
                error_preview += "..."
            lines.append(f"   错误: {error_preview}")
    
    lines.append("\n延迟: ms, Token: 个")
    
    return "\n".join(lines)


def detect_platform(event) -> str:
    """
    检测事件来源平台
    
    Args:
        event: Gateway 事件对象
    
    Returns:
        平台标识 "feishu" 或 "weixin"
    """
    # 从 event 对象获取平台信息
    platform_name = getattr(event, 'platform', None)
    
    if platform_name:
        platform_name = platform_name.lower()
        if 'feishu' in platform_name or 'lark' in platform_name:
            return "feishu"
        if 'weixin' in platform_name or 'wechat' in platform_name:
            return "weixin"
    
    # 从 source 对象获取
    source = getattr(event, 'source', None)
    if source:
        source_type = type(source).__name__.lower()
        if 'feishu' in source_type or 'lark' in source_type:
            return "feishu"
        if 'weixin' in source_type or 'wechat' in source_type:
            return "weixin"
    
    # 默认返回飞书格式（支持 Markdown）
    return "feishu"


def format_active_tasks(tasks: list, platform: str = "feishu") -> str:
    """格式化活跃任务列表"""
    if not tasks:
        return "暂无活跃任务"
    
    if platform == "feishu":
        lines = [
            "**🔄 活跃任务**",
            f"共 {len(tasks)} 个任务正在执行",
            "",
        ]
        for task in tasks:
            task_id = task.task_id[:8]
            status_icon = STATUS_ICONS.get(task.status, "⏳")
            status_cn = STATUS_CN.get(task.status, task.status.value)
            title = (task.title or "无标题")[:30]
            lines.append(f"{status_icon} **{task_id}** `{status_cn}` {title}")
    else:
        lines = [
            "【活跃任务】",
            f"共 {len(tasks)} 个",
            "",
        ]
        for task in tasks:
            task_id = task.task_id[:8]
            status_icon = STATUS_ICONS.get(task.status, "⏳")
            status_cn = STATUS_CN.get(task.status, task.status.value)
            title = (task.title or "无标题")[:25]
            lines.append(f"{status_icon} {task_id} [{status_cn}] {title}")
    
    return "\n".join(lines)


def format_failed_tasks(tasks: list, platform: str = "feishu") -> str:
    """格式化失败任务列表"""
    if not tasks:
        return "暂无失败任务 ✅"
    
    if platform == "feishu":
        lines = [
            "**❌ 失败任务**",
            f"共 {len(tasks)} 个任务失败",
            "",
        ]
        for task in tasks[:10]:  # 最多显示10个
            task_id = task.task_id[:8]
            title = (task.title or "无标题")[:30]
            error = task.error_message[:50] if hasattr(task, 'error_message') and task.error_message else "未知错误"
            lines.append(f"❌ **{task_id}** {title}")
            lines.append(f"   错误: {error}")
    else:
        lines = [
            "【失败任务】",
            f"共 {len(tasks)} 个",
            "",
        ]
        for task in tasks[:10]:
            task_id = task.task_id[:8]
            title = (task.title or "无标题")[:25]
            error = task.error_message[:40] if hasattr(task, 'error_message') and task.error_message else "未知错误"
            lines.append(f"✗ {task_id} {title}")
            lines.append(f"  错误: {error}")
    
    return "\n".join(lines)


def format_task_events(events: list, task_id: str, platform: str = "feishu") -> str:
    """格式化任务事件流"""
    if not events:
        return f"暂无事件记录: {task_id}"
    
    if platform == "feishu":
        lines = [
            f"**📜 任务事件流** `{task_id}`",
            "",
            "```",
        ]
        for event in events:
            time_str = event.get('time', '')[:19] if event.get('time') else ''
            event_type = event.get('type', '')
            message = event.get('message', '')
            icon = {
                'task_created': '📥',
                'classified': '👑',
                'plan_completed': '📋',
                'review_completed': '🔍',
                'dispatched': '📤',
                'agent_started': '🔧',
                'agent_completed': '✅',
                'task_completed': '🎉',
                'task_failed': '❌',
            }.get(event_type, '•')
            lines.append(f"{time_str} {icon} {message}")
        lines.append("```")
    else:
        lines = [
            f"【事件流】{task_id}",
            "",
        ]
        for event in events:
            time_str = event.get('time', '')[:19] if event.get('time') else ''
            message = event.get('message', '')
            lines.append(f"{time_str} {message}")
    
    return "\n".join(lines)


def format_workspace(workspace_path: str, files: list, task_id: str, platform: str = "feishu") -> str:
    """格式化工作空间信息"""
    if platform == "feishu":
        lines = [
            f"**📁 任务工作空间** `{task_id}`",
            "",
            f"**路径**: `{workspace_path}`",
            "",
            "**产出文件**:",
            "```",
        ]
        for f in files[:20]:
            lines.append(f"├── {f}")
        lines.append("```")
    else:
        lines = [
            f"【工作空间】{task_id}",
            "",
            f"路径: {workspace_path}",
            "",
            "产出文件:",
        ]
        for f in files[:15]:
            lines.append(f"  {f}")
    
    return "\n".join(lines)


def format_notification(notification_type: str, data: dict, platform: str = "feishu") -> str:
    """
    格式化推送通知
    
    Args:
        notification_type: 通知类型 (task_started, review_approved, task_completed, etc.)
        data: 通知数据
        platform: 平台类型
    """
    if platform == "feishu":
        return _format_notification_feishu(notification_type, data)
    else:
        return _format_notification_weixin(notification_type, data)


def _format_notification_feishu(notification_type: str, data: dict) -> str:
    """飞书格式通知"""
    if notification_type == "task_started":
        return "\n".join([
            "📥 **新任务开始**",
            "",
            f"> 标题：{data.get('title', '无标题')}",
            f"> 类型：{data.get('type', '旨意')}",
            f"> 时间：{data.get('time', '')}",
            "",
            "正在分拣处理...",
        ])
    
    elif notification_type == "review_approved":
        return "\n".join([
            "🔍 **门下省审议结果**",
            "",
            f"> 决定：✅ 通过",
            f"> 轮次：第 {data.get('round', 1)} 轮",
            "",
            "方案已批准，即将派发执行。",
        ])
    
    elif notification_type == "review_rejected":
        return "\n".join([
            "🔍 **门下省审议结果**",
            "",
            f"> 决定：⚠️ 封驳",
            f"> 轮次：第 {data.get('round', 1)} 轮",
            f"> 原因：{data.get('reason', '需要修改')}",
            "",
            "中书省正在修改方案...",
        ])
    
    elif notification_type == "dispatched":
        agents = data.get('agents', [])
        agents_str = "、".join(agents) if agents else "待定"
        return "\n".join([
            "📤 **尚书省派发**",
            "",
            f"> 已派发给：{agents_str}",
            "",
            "六部正在执行...",
        ])
    
    elif notification_type == "agent_completed":
        return "\n".join([
            f"✅ **{data.get('agent', 'Agent')} 完成**",
            "",
            f"> 摘要：{data.get('summary', '执行完成')}",
            "",
            f"查看详情：/tasks {data.get('task_id', '')[:8]}",
        ])
    
    elif notification_type == "task_completed":
        return "\n".join([
            "🎉 **任务完成**",
            "",
            f"> 标题：{data.get('title', '')}",
            f"> 耗时：{data.get('duration', '')}",
            f"> Token：{data.get('tokens', 0)}",
            "",
            f"**执行摘要**",
            data.get('summary', '任务已完成'),
            "",
            f"查看详情：/tasks {data.get('task_id', '')[:8]}",
        ])
    
    elif notification_type == "task_failed":
        return "\n".join([
            "❌ **任务失败**",
            "",
            f"> 标题：{data.get('title', '')}",
            f"> 原因：{data.get('reason', '未知错误')}",
            "",
            f"查看详情：/tasks {data.get('task_id', '')[:8]}",
        ])
    
    return f"通知: {notification_type}"


def _format_notification_weixin(notification_type: str, data: dict) -> str:
    """微信格式通知"""
    if notification_type == "task_started":
        return "\n".join([
            "【新任务开始】",
            "",
            f"标题: {data.get('title', '无标题')}",
            f"类型: {data.get('type', '旨意')}",
            "",
            "正在分拣处理...",
        ])
    
    elif notification_type == "review_approved":
        return "\n".join([
            "【审议通过】",
            "",
            f"轮次: 第{data.get('round', 1)}轮",
            "",
            "方案已批准，即将派发执行。",
        ])
    
    elif notification_type == "review_rejected":
        return "\n".join([
            "【审议封驳】",
            "",
            f"轮次: 第{data.get('round', 1)}轮",
            f"原因: {data.get('reason', '需要修改')}",
            "",
            "中书省正在修改方案...",
        ])
    
    elif notification_type == "dispatched":
        agents = data.get('agents', [])
        agents_str = "、".join(agents) if agents else "待定"
        return "\n".join([
            "【已派发】",
            "",
            f"派发给: {agents_str}",
            "",
            "六部正在执行...",
        ])
    
    elif notification_type == "task_completed":
        return "\n".join([
            "【任务完成】",
            "",
            f"标题: {data.get('title', '')}",
            f"耗时: {data.get('duration', '')}",
            f"Token: {data.get('tokens', 0)}",
            "",
            f"查看: /tasks {data.get('task_id', '')[:8]}",
        ])
    
    elif notification_type == "task_failed":
        return "\n".join([
            "【任务失败】",
            "",
            f"标题: {data.get('title', '')}",
            f"原因: {data.get('reason', '未知错误')}",
            "",
            f"查看: /tasks {data.get('task_id', '')[:8]}",
        ])
    
    return f"通知: {notification_type}"


def format_daily_report(stats: dict, platform: str = "feishu") -> str:
    """格式化日报"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    if platform == "feishu":
        lines = [
            f"📊 **多Agent日报** `{today}`",
            "",
            "---",
            "",
            "**📈 今日数据**",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 新增任务 | {stats.get('new_tasks', 0)} |",
            f"| 完成任务 | {stats.get('completed_tasks', 0)} |",
            f"| 进行中 | {stats.get('active_tasks', 0)} |",
            f"| 失败 | {stats.get('failed_tasks', 0)} |",
            f"| 成功率 | {stats.get('success_rate', 0)}% |",
            f"| Token消耗 | {stats.get('tokens_used', 0):,} |",
            "",
            "---",
            "",
            "**🔥 活跃 Agent**",
            "",
        ]
        
        agents = stats.get('top_agents', [])
        for i, agent in enumerate(agents[:3], 1):
            lines.append(f"{i}. {agent.get('name', '')} - {agent.get('calls', 0)}次 - {agent.get('tokens', 0):,} token")
        
        # 进行中任务
        active = stats.get('active_task_list', [])
        if active:
            lines.extend([
                "",
                "---",
                "",
                "**📋 进行中任务**",
            ])
            for task in active[:5]:
                lines.append(f"• {task.get('id', '')[:8]}: {task.get('title', '')} ({task.get('status', '')})")
        
        lines.extend([
            "",
            f"`查看详情：/tasks active`",
        ])
    else:
        lines = [
            f"📊 多Agent日报 ({today})",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "【今日数据】",
            f"新增: {stats.get('new_tasks', 0)} | 完成: {stats.get('completed_tasks', 0)}",
            f"进行中: {stats.get('active_tasks', 0)} | 失败: {stats.get('failed_tasks', 0)}",
            f"成功率: {stats.get('success_rate', 0)}%",
            f"Token: {stats.get('tokens_used', 0):,}",
            "",
            "【活跃 Agent】",
        ]
        
        agents = stats.get('top_agents', [])
        for agent in agents[:3]:
            lines.append(f"{agent.get('name', '')} {agent.get('calls', 0)}次 | {agent.get('tokens', 0):,}t")
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            "/tasks active 查看详情",
        ])
    
    return "\n".join(lines)


def format_weekly_report(stats: dict, platform: str = "feishu") -> str:
    """格式化周报"""
    from datetime import datetime
    
    # 计算周数
    today = datetime.now()
    week_num = today.isocalendar()[1]
    year = today.year
    
    if platform == "feishu":
        lines = [
            f"📊 **多Agent周报** `{year}年第{week_num}周`",
            "",
            "---",
            "",
            "**📈 本周数据**",
            "",
            "| 指标 | 数值 | 环比 |",
            "|------|------|------|",
            f"| 新增任务 | {stats.get('new_tasks', 0)} | {stats.get('new_tasks_change', '-')} |",
            f"| 完成任务 | {stats.get('completed_tasks', 0)} | {stats.get('completed_change', '-')} |",
            f"| 成功率 | {stats.get('success_rate', 0)}% | {stats.get('success_rate_change', '-')} |",
            f"| 总Token | {stats.get('tokens_used', 0):,} | {stats.get('tokens_change', '-')} |",
            f"| 平均耗时 | {stats.get('avg_duration', '-')} | {stats.get('duration_change', '-')} |",
            "",
            "---",
            "",
            "**🏆 Agent 排行榜**",
            "",
            "| 排名 | Agent | 调用 | Token | 成功率 |",
            "|------|-------|------|-------|--------|",
        ]
        
        agents = stats.get('top_agents', [])
        medals = ["🥇", "🥈", "🥉"]
        for i, agent in enumerate(agents[:3]):
            medal = medals[i] if i < 3 else ""
            lines.append(f"| {medal} | {agent.get('name', '')} | {agent.get('calls', 0)} | {agent.get('tokens', 0):,} | {agent.get('success_rate', 0)}% |")
        
        lines.extend([
            "",
            "---",
            "",
            "**💡 系统建议**",
            "• 成功率稳定在 90%+，系统运行良好",
            "",
            f"`查看详情：/tasks stats`",
        ])
    else:
        lines = [
            f"📊 多Agent周报 ({year}年第{week_num}周)",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "【本周数据】",
            f"新增: {stats.get('new_tasks', 0)} | 完成: {stats.get('completed_tasks', 0)}",
            f"成功率: {stats.get('success_rate', 0)}% | Token: {stats.get('tokens_used', 0):,}",
            "",
            "【Agent 排行】",
        ]
        
        agents = stats.get('top_agents', [])
        medals = ["🥇", "🥈", "🥉"]
        for i, agent in enumerate(agents[:3]):
            medal = medals[i] if i < 3 else ""
            lines.append(f"{medal} {agent.get('name', '')} - {agent.get('calls', 0)}次 - {agent.get('success_rate', 0)}%")
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            "/tasks stats 查看详情",
        ])
    
    return "\n".join(lines)
