"""首次启动从 .env / project_names.json 导入配置。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from work_report.config import DEFAULT_PROJECT_NAMES_FILE, ROOT_DIR, load_project_name_map
from work_report.db.models import AppSetting, Holiday, ProjectName, utcnow
from work_report.default_prompts import DEFAULT_WEEKLY_REPORT_PROMPT

logger = logging.getLogger(__name__)

# 写入 app_settings 的键（与前端 / Settings 对齐，小写 snake）
SETTING_KEYS = [
    "gitlab_url",
    "gitlab_token",
    "author_email",
    "project_ids",
    "llm_api_key",
    "llm_base_url",
    "llm_model",
    "llm_timeout",
    "llm_system_prompt",
    "timezone_offset_hours",
    "dingtalk_webhook",
    "dingtalk_secret",
    "dingtalk_timeout",
    "schedule_time",
    "schedule_days",
]

# .env 大写名映射
ENV_KEY_MAP = {
    "gitlab_url": "GITLAB_URL",
    "gitlab_token": "GITLAB_TOKEN",
    "author_email": "AUTHOR_EMAIL",
    "project_ids": "PROJECT_IDS",
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "llm_timeout": "LLM_TIMEOUT",
    "llm_system_prompt": "LLM_SYSTEM_PROMPT",
    "timezone_offset_hours": "TIMEZONE_OFFSET_HOURS",
    "dingtalk_webhook": "DINGTALK_WEBHOOK",
    "dingtalk_secret": "DINGTALK_SECRET",
    "dingtalk_timeout": "DINGTALK_TIMEOUT",
    "schedule_time": "SCHEDULE_TIME",
    "schedule_days": "SCHEDULE_DAYS",
}

DEFAULTS = {
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4o-mini",
    "llm_timeout": "120",
    "llm_system_prompt": DEFAULT_WEEKLY_REPORT_PROMPT,
    "timezone_offset_hours": "8",
    "dingtalk_timeout": "15",
    "schedule_time": "17:30",
    "schedule_days": "Mon,Tue,Wed,Thu,Fri",
}


def seed_if_empty(session: Session, env_file: str | Path | None = None) -> None:
    """分别为尚无数据的配置、项目名称和节假日表导入默认值。"""
    now = utcnow()

    setting_count = session.scalar(select(func.count()).select_from(AppSetting)) or 0
    if setting_count == 0:
        path = Path(env_file) if env_file else ROOT_DIR / ".env"
        load_dotenv(path, override=False)
        logger.info("空配置表 seed：从 %s 导入配置", path)
        for key in SETTING_KEYS:
            env_name = ENV_KEY_MAP[key]
            value = os.getenv(env_name, "").strip()
            if not value:
                value = DEFAULTS.get(key, "")
            session.add(AppSetting(key=key, value=value, updated_at=now))

    name_count = session.scalar(select(func.count()).select_from(ProjectName)) or 0
    if name_count == 0:
        mapping = load_project_name_map(DEFAULT_PROJECT_NAMES_FILE)
        for project_key, display_name in mapping.items():
            session.add(
                ProjectName(
                    project_key=project_key,
                    display_name=display_name,
                    updated_at=now,
                )
            )
        logger.info("已导入项目中文名映射 %s 条", len(mapping))

    holiday_count = session.scalar(select(func.count()).select_from(Holiday)) or 0
    if holiday_count == 0:
        for item in DEFAULT_HOLIDAYS:
            session.add(
                Holiday(
                    date=item["date"],
                    description=item["description"],
                    is_makeup=item["is_makeup"],
                )
            )
        logger.info("已导入节假日 %s 条", len(DEFAULT_HOLIDAYS))

    session.flush()


DEFAULT_HOLIDAYS = [
    {"date": "2026-01-01", "description": "元旦", "is_makeup": False},
    {"date": "2026-01-02", "description": "元旦", "is_makeup": False},
    {"date": "2026-01-03", "description": "元旦", "is_makeup": False},
    {"date": "2026-01-04", "description": "元旦调休", "is_makeup": True},
    {"date": "2026-02-14", "description": "春节调休", "is_makeup": True},
    {"date": "2026-02-15", "description": "春节", "is_makeup": False},
    {"date": "2026-02-16", "description": "春节", "is_makeup": False},
    {"date": "2026-02-17", "description": "春节", "is_makeup": False},
    {"date": "2026-02-18", "description": "春节", "is_makeup": False},
    {"date": "2026-02-19", "description": "春节", "is_makeup": False},
    {"date": "2026-02-20", "description": "春节", "is_makeup": False},
    {"date": "2026-02-21", "description": "春节", "is_makeup": False},
    {"date": "2026-02-22", "description": "春节", "is_makeup": False},
    {"date": "2026-02-23", "description": "春节", "is_makeup": False},
    {"date": "2026-02-28", "description": "春节调休", "is_makeup": True},
    {"date": "2026-04-04", "description": "清明节", "is_makeup": False},
    {"date": "2026-04-05", "description": "清明节", "is_makeup": False},
    {"date": "2026-04-06", "description": "清明节", "is_makeup": False},
    {"date": "2026-05-01", "description": "劳动节", "is_makeup": False},
    {"date": "2026-05-02", "description": "劳动节", "is_makeup": False},
    {"date": "2026-05-03", "description": "劳动节", "is_makeup": False},
    {"date": "2026-05-04", "description": "劳动节", "is_makeup": False},
    {"date": "2026-05-05", "description": "劳动节", "is_makeup": False},
    {"date": "2026-05-09", "description": "劳动节调休", "is_makeup": True},
    {"date": "2026-06-19", "description": "端午节", "is_makeup": False},
    {"date": "2026-06-20", "description": "端午节", "is_makeup": False},
    {"date": "2026-06-21", "description": "端午节", "is_makeup": False},
    {"date": "2026-09-20", "description": "国庆调休", "is_makeup": True},
    {"date": "2026-09-25", "description": "中秋节", "is_makeup": False},
    {"date": "2026-09-26", "description": "中秋节", "is_makeup": False},
    {"date": "2026-09-27", "description": "中秋节", "is_makeup": False},
    {"date": "2026-10-01", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-02", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-03", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-04", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-05", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-06", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-07", "description": "国庆节", "is_makeup": False},
    {"date": "2026-10-10", "description": "国庆调休", "is_makeup": True},
]
