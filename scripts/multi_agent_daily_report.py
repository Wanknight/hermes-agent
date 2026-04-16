#!/usr/bin/env python3
"""
多Agent日报生成脚本

由 cron 系统定时调用，生成每日报告并通过 gateway 发送给用户。
"""

import json
import sys
import os

# 确保可以导入父目录的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from datetime import datetime

# 导入报告生成器
from multi_agent.report_generator import (
    generate_daily_report,
    collect_daily_stats,
    get_active_tasks,
    get_failed_tasks_today,
    get_agent_stats_today,
)
from multi_agent import MultiAgentOrchestrator


def main():
    """生成日报"""
    # 获取平台类型（从环境变量或默认飞书）
    platform = os.getenv("HERMES_REPORT_PLATFORM", "feishu")
    
    # 创建 orchestrator
    try:
        orchestrator = MultiAgentOrchestrator()
    except Exception as e:
        print(f"[ERROR] 无法初始化 MultiAgentOrchestrator: {e}")
        sys.exit(1)
    
    try:
        # 收集统计数据
        stats = collect_daily_stats(orchestrator)
        
        # 获取进行中和失败的任务
        active_tasks = get_active_tasks(orchestrator)
        failed_tasks = get_failed_tasks_today(orchestrator)
        
        # Agent 统计
        agent_stats = get_agent_stats_today(orchestrator)
        
        # 生成报告
        report = generate_daily_report(
            stats=stats,
            active_tasks=active_tasks,
            failed_tasks=failed_tasks,
            agent_stats=agent_stats,
            platform=platform,
        )
        
        # 输出到 stdout，由 cron 系统处理
        print(report)
        
    except Exception as e:
        print(f"[ERROR] 生成日报失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
