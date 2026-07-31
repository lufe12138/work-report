"""系统 / 仪表盘 / 健康检查。"""

from __future__ import annotations

from datetime import date as calendar_date
from typing import Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from work_report.api.deps import DbSession
from work_report.holiday import check_last_workday_before_holiday
from work_report.services import run_service, settings_service
from work_report.services.holiday_sync_service import (
    OfficialHolidayNotFoundError,
    OfficialHolidaySyncError,
    fetch_official_holiday_schedule,
)
from work_report.timeutil import now

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
    result = check_last_workday_before_holiday(
        tz_offset_hours=tz,
        workday_overrides=settings_service.get_special_dates(db),
    )
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


class HolidayItem(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(max_length=128)
    is_makeup: bool = False

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        try:
            calendar_date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("日期必须是有效的 YYYY-MM-DD 日期") from exc
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("描述不能为空")
        return normalized


class HolidayList(BaseModel):
    items: list[HolidayItem]

    @model_validator(mode="after")
    def validate_unique_dates(self) -> Self:
        dates = [item.date for item in self.items]
        if len(dates) != len(set(dates)):
            raise ValueError("节假日日期不能重复")
        return self


class HolidaySyncRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)


@router.get("/holidays")
def get_holidays(db: DbSession) -> dict:
    return {"items": settings_service.list_holidays(db)}


@router.put("/holidays")
def put_holidays(body: HolidayList, db: DbSession) -> dict:
    items = [i.model_dump() for i in body.items]
    return {"items": settings_service.save_holidays(db, items)}


@router.post("/holidays")
def post_holiday(body: HolidayItem, db: DbSession) -> dict:
    settings_service.upsert_holiday(
        db,
        body.date,
        body.description,
        body.is_makeup,
    )
    return {"ok": True, "item": body.model_dump()}


@router.post("/holidays/sync-official")
def sync_official_holidays(body: HolidaySyncRequest, db: DbSession) -> dict:
    try:
        schedule = fetch_official_holiday_schedule(body.year)
    except OfficialHolidayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OfficialHolidaySyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    items = settings_service.save_holidays_for_year(
        db,
        schedule.year,
        schedule.items,
    )
    return {
        "year": schedule.year,
        "source_url": schedule.source_url,
        "count": len(schedule.items),
        "items": items,
    }


@router.delete("/holidays/past")
def delete_past_holidays(db: DbSession) -> dict:
    cutoff_date = now().date().isoformat()
    deleted = settings_service.delete_holidays_before(db, cutoff_date)
    return {
        "cutoff_date": cutoff_date,
        "deleted": deleted,
        "items": settings_service.list_holidays(db),
    }


@router.delete("/holidays/{date}")
def delete_holiday_route(date: str, db: DbSession) -> dict:
    ok = settings_service.delete_holiday(db, date)
    if not ok:
        raise HTTPException(status_code=404, detail="节假日不存在")
    return {"ok": True}
