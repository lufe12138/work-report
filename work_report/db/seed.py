"""首次启动从 .env / project_names.json 导入配置。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from work_report.config import DEFAULT_PROJECT_NAMES_FILE, ROOT_DIR, load_project_name_map
from work_report.db.models import AppSetting, ProjectName, utcnow

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
    "timezone_offset_hours": "8",
    "dingtalk_timeout": "15",
    "schedule_time": "17:30",
    "schedule_days": "Mon,Tue,Wed,Thu,Fri",
}


def seed_if_empty(session: Session, env_file: str | Path | None = None) -> None:
    """仅当 app_settings 无任何行时导入。"""
    count = session.scalar(select(func.count()).select_from(AppSetting)) or 0
    if count > 0:
        return

    path = Path(env_file) if env_file else ROOT_DIR / ".env"
    load_dotenv(path, override=False)
    logger.info("空库 seed：从 %s 与 project_names 导入配置", path)

    now = utcnow()
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

    session.flush()
