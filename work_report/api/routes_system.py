"""系统 / 仪表盘 / 健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from work_report.api.deps import DbSession
from work_report.holiday import check_last_workday_before_holiday
from work_report.services import run_service, settings_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/system/holiday")
def holiday_status(db: DbSession) -> dict:
    raw = settings_service.get_all_settings_map(db)
    try:
        tz = int(raw.get("timezone_offset_hours") or 8)
    except ValueError:
        tz = 8
    result = check_last_workday_before_holiday(tz_offset_hours=tz)
    return result.to_dict()


@router.get("/dashboard")
def dashboard(db: DbSession) -> dict:
    data = run_service.dashboard(db)
    public = settings_service.get_public_config(db)
    required = ["gitlab_url", "gitlab_token", "author_email", "project_ids", "llm_api_key"]
    config_ready = True
    for key in required:
        val = public.get(key)
        if isinstance(val, dict):
            if not val.get("configured"):
                config_ready = False
        elif not val:
            config_ready = False
    data["config_ready"] = config_ready
    try:
        holiday = holiday_status(db)
        data["holiday"] = holiday
    except Exception as exc:  # noqa: BLE001
        data["holiday"] = {"error": str(exc)}
    return data
