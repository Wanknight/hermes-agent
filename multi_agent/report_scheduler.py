"""
多Agent定时报告注册

在 Gateway 启动时自动注册日报/周报定时任务。
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def register_multi_agent_reports(config: Optional[Dict[str, Any]] = None) -> None:
    """
    注册多Agent日报/周报定时任务
    
    根据 config.yaml 中的 multi_agent.reports 配置自动注册定时任务。
    如果任务已存在，则跳过注册。
    
    Args:
        config: 配置字典（可选，默认从配置文件加载）
    """
    from cron.jobs import load_jobs, create_job, get_job
    from hermes_cli.config import load_config
    from hermes_constants import get_hermes_home
    
    # 加载配置
    if config is None:
        config = load_config() or {}
    
    multi_agent_config = config.get("multi_agent", {})
    reports_config = multi_agent_config.get("reports", {})
    
    # 检查是否启用
    if not multi_agent_config.get("enabled", False):
        logger.debug("Multi-agent mode disabled, skipping report registration")
        return
    
    # 获取脚本目录
    scripts_dir = get_hermes_home() / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    
    # 注册日报
    daily_config = reports_config.get("daily", {})
    if daily_config.get("enabled", True):
        _register_daily_report(daily_config, scripts_dir)
    
    # 注册周报
    weekly_config = reports_config.get("weekly", {})
    if weekly_config.get("enabled", True):
        _register_weekly_report(weekly_config, scripts_dir)


def _register_daily_report(config: Dict[str, Any], scripts_dir) -> None:
    """注册日报定时任务"""
    from cron.jobs import load_jobs, create_job
    
    # 检查是否已存在
    jobs = load_jobs()
    existing = [j for j in jobs if j.get("name") == "多Agent日报"]
    if existing:
        logger.debug("Daily report job already exists, skipping registration")
        return
    
    # 解析时间配置
    time_str = config.get("time", "09:30")
    hour, minute = _parse_time(time_str)
    
    # 创建 cron 表达式：每天指定时间
    cron_expr = f"{minute} {hour} * * *"
    
    # 脚本路径
    script_path = "multi_agent_daily_report.py"
    
    try:
        job = create_job(
            prompt="生成多Agent日报",
            schedule=cron_expr,
            name="多Agent日报",
            script=script_path,
            repeat=None,  # 无限重复
            deliver="origin",
        )
        logger.info("Registered daily report job: %s (cron: %s)", job["id"], cron_expr)
    except Exception as e:
        logger.warning("Failed to register daily report job: %s", e)


def _register_weekly_report(config: Dict[str, Any], scripts_dir) -> None:
    """注册周报定时任务"""
    from cron.jobs import load_jobs, create_job
    
    # 检查是否已存在
    jobs = load_jobs()
    existing = [j for j in jobs if j.get("name") == "多Agent周报"]
    if existing:
        logger.debug("Weekly report job already exists, skipping registration")
        return
    
    # 解析时间配置
    time_str = config.get("time", "09:30")
    hour, minute = _parse_time(time_str)
    
    # 解析星期配置
    day_str = config.get("day", "monday")
    weekday = _parse_weekday(day_str)
    
    # 创建 cron 表达式：每周指定星期和时间
    # cron 格式: minute hour day month weekday
    cron_expr = f"{minute} {hour} * * {weekday}"
    
    # 脚本路径
    script_path = "multi_agent_weekly_report.py"
    
    try:
        job = create_job(
            prompt="生成多Agent周报",
            schedule=cron_expr,
            name="多Agent周报",
            script=script_path,
            repeat=None,  # 无限重复
            deliver="origin",
        )
        logger.info("Registered weekly report job: %s (cron: %s)", job["id"], cron_expr)
    except Exception as e:
        logger.warning("Failed to register weekly report job: %s", e)


def _parse_time(time_str: str) -> tuple:
    """
    解析时间字符串
    
    Args:
        time_str: 时间字符串，格式为 "HH:MM"
    
    Returns:
        (hour, minute) 元组
    """
    try:
        parts = time_str.split(":")
        if len(parts) == 2:
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
    except (ValueError, AttributeError):
        pass
    
    # 默认 09:30
    logger.warning("Invalid time format '%s', using default 09:30", time_str)
    return 9, 30


def _parse_weekday(day_str: str) -> int:
    """
    解析星期字符串
    
    Args:
        day_str: 星期字符串，如 "monday", "tuesday" 等
    
    Returns:
        cron 格式的星期数字 (0=周日, 1=周一, ..., 6=周六)
    """
    day_map = {
        "sunday": 0,
        "sun": 0,
        "monday": 1,
        "mon": 1,
        "tuesday": 2,
        "tue": 2,
        "wednesday": 3,
        "wed": 3,
        "thursday": 4,
        "thu": 4,
        "friday": 5,
        "fri": 5,
        "saturday": 6,
        "sat": 6,
    }
    
    day_lower = day_str.lower().strip()
    if day_lower in day_map:
        return day_map[day_lower]
    
    # 默认周一
    logger.warning("Unknown weekday '%s', using default (monday)", day_str)
    return 1
