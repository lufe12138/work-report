"""跨平台周报定时调度服务。"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import tzinfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from work_report.db.session import session_scope
from work_report.pipeline import RunOptions, run_pipeline
from work_report.services import settings_service
from work_report.timeutil import tz_from_offset_hours

logger = logging.getLogger(__name__)

SCHEDULED_REPORT_JOB_ID = "weekly-report"

_DAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "周一": "mon",
    "1": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "周二": "tue",
    "2": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "周三": "wed",
    "3": "wed",
    "thu": "thu",
    "thursday": "thu",
    "周四": "thu",
    "4": "thu",
    "fri": "fri",
    "friday": "fri",
    "周五": "fri",
    "5": "fri",
    "sat": "sat",
    "saturday": "sat",
    "周六": "sat",
    "6": "sat",
    "sun": "sun",
    "sunday": "sun",
    "周日": "sun",
    "0": "sun",
    "7": "sun",
}
_DAY_LABELS = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}
_scheduler_lock = threading.RLock()
_scheduler: BackgroundScheduler | None = None


@dataclass(frozen=True)
class ScheduleConfig:
    """经过校验的调度配置。"""

    hour: int
    minute: int
    days: tuple[str, ...]
    timezone: tzinfo
    timezone_offset_hours: int

    @property
    def day_expression(self) -> str:
        return ",".join(self.days)

    @property
    def time_text(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


def normalize_schedule_time(value: str) -> str:
    """校验并规范化 HH:mm 时间。"""
    match = re.fullmatch(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})", value.strip())
    if match is None:
        raise ValueError("定时时间格式必须为 HH:mm，例如 17:30")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("定时时间超出有效范围")
    return f"{hour:02d}:{minute:02d}"


def normalize_schedule_days(value: str) -> str:
    """校验并规范化星期列表。"""
    normalized: list[str] = []
    for part in re.split(r"[,;，\s]+", value.strip()):
        if not part:
            continue
        day = _DAY_ALIASES.get(part.casefold())
        if day is None:
            raise ValueError(
                f"无法识别定时星期：{part}，请使用 Mon,Tue,Wed,Thu,Fri,Sat,Sun"
            )
        if day not in normalized:
            normalized.append(day)
    if not normalized:
        raise ValueError("定时星期不能为空")
    return ",".join(_DAY_LABELS[day] for day in normalized)


def normalize_timezone_offset(value: str | int) -> int:
    """校验时区偏移小时数。"""
    try:
        offset = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("时区偏移必须是整数") from exc
    if not -12 <= offset <= 14:
        raise ValueError("时区偏移必须在 -12 到 14 之间")
    return offset


def parse_schedule_config(raw: dict[str, str]) -> ScheduleConfig:
    """从数据库配置解析调度参数。"""
    time_text = normalize_schedule_time(raw.get("schedule_time") or "17:30")
    days_text = normalize_schedule_days(
        raw.get("schedule_days") or "Mon,Tue,Wed,Thu,Fri"
    )
    timezone_offset = normalize_timezone_offset(
        raw.get("timezone_offset_hours") or 8
    )
    hour_text, minute_text = time_text.split(":", 1)
    days = tuple(day.casefold() for day in days_text.split(","))
    return ScheduleConfig(
        hour=int(hour_text),
        minute=int(minute_text),
        days=days,
        timezone=tz_from_offset_hours(timezone_offset),
        timezone_offset_hours=timezone_offset,
    )


def _load_schedule_config() -> ScheduleConfig:
    with session_scope() as session:
        raw = settings_service.get_all_settings_map(session)
    return parse_schedule_config(raw)


def _run_scheduled_report() -> None:
    logger.info("定时周报任务开始")
    try:
        result = run_pipeline(
            RunOptions(
                skip_llm=False,
                send_dingtalk=True,
                if_last_workday=True,
                trigger="schedule",
            )
        )
    except Exception:  # noqa: BLE001
        logger.exception("定时周报任务出现未处理异常")
        return
    if result.status == "failed":
        logger.error(
            "定时周报任务失败: run_id=%s error=%s",
            result.run_id,
            result.error_message,
        )
        return
    logger.info(
        "定时周报任务结束: run_id=%s status=%s",
        result.run_id,
        result.status,
    )


def reload_schedule() -> ScheduleConfig:
    """重新读取配置，并替换当前定时任务。"""
    config = _load_schedule_config()
    trigger = CronTrigger(
        day_of_week=config.day_expression,
        hour=config.hour,
        minute=config.minute,
        timezone=config.timezone,
    )

    with _scheduler_lock:
        if _scheduler is None:
            return config
        job = _scheduler.add_job(
            _run_scheduled_report,
            trigger=trigger,
            id=SCHEDULED_REPORT_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )
    logger.info(
        "定时周报已更新: days=%s time=%s timezone=UTC%+d next_run=%s",
        config.day_expression,
        config.time_text,
        config.timezone_offset_hours,
        job.next_run_time.isoformat(timespec="seconds"),
    )
    return config


def start_scheduler() -> None:
    """启动进程内 APScheduler 并加载数据库配置。"""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            return
        scheduler = BackgroundScheduler()
        scheduler.start()
        _scheduler = scheduler

    try:
        reload_schedule()
    except ValueError:
        logger.exception("定时配置无效，调度任务未启用，请在系统配置中修正")
    except Exception:  # noqa: BLE001
        logger.exception("启动定时调度器失败")


def shutdown_scheduler(*, wait: bool = False) -> None:
    """停止进程内调度器。"""
    global _scheduler
    with _scheduler_lock:
        scheduler = _scheduler
        _scheduler = None
    if scheduler is not None:
        scheduler.shutdown(wait=wait)
        logger.info("定时调度器已停止")
