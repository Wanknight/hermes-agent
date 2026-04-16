#!/usr/bin/env python3
"""
多Agent周报生成脚本

由 cron 系统定时调用，生成每周报告并通过 gateway 发送给用户。
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
    generate_weekly_report,
    collect_weekly_stats,
    collect_daily_trend,
    collect_agent_ranking,
    generate_suggestions,
)
from multi_agent import MultiAgentOrchestrator


def main():
    """生成周报"""
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
        stats = collect_weekly_stats(orchestrator)
        
        # 收集每日趋势
        daily_trend = collect_daily_trend(orchestrator)
        
        # 收集 Agent 排行
        agent_ranking = collect_agent_ranking(orchestrator)
        
        # 生成建议
        suggestions = generate_suggestions(stats, agent_ranking)
        
        # 生成报告
        report = generate_weekly_report(
            stats=stats,
            daily_trend=daily_trend,
            agent_ranking=agent_ranking,
            suggestions=suggestions,
            platform=platform,
        )
        
        # 输出到 stdout，由 cron 系统处理
        print(report)
        
    except Exception as e:
        print(f"[ERROR] 生成周报失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
