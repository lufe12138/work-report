"""配置读写与密钥脱敏。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from work_report.config import Settings
from work_report.db.models import AppSetting, Holiday, ProjectName, utcnow
from work_report.db.seed import DEFAULTS, SETTING_KEYS

SECRET_KEYS = frozenset(
    {
        "gitlab_token",
        "llm_api_key",
        "dingtalk_webhook",
        "dingtalk_secret",
    }
)

MASK = "********"


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return MASK
    return f"{MASK}{value[-4:]}"


def get_all_settings_map(session: Session) -> dict[str, str]:
    rows = session.scalars(select(AppSetting)).all()
    result = {k: DEFAULTS.get(k, "") for k in SETTING_KEYS}
    for row in rows:
        result[row.key] = row.value or ""
    return result


def get_project_name_map(session: Session) -> dict[str, str]:
    rows = session.scalars(select(ProjectName)).all()
    return {r.project_key: r.display_name for r in rows if r.project_key and r.display_name}


def get_public_config(session: Session) -> dict[str, Any]:
    raw = get_all_settings_map(session)
    public: dict[str, Any] = {}
    for key in SETTING_KEYS:
        value = raw.get(key, "")
        if key in SECRET_KEYS:
            public[key] = {
                "configured": bool(value),
                "masked": _mask_secret(value) if value else "",
            }
        else:
            public[key] = value
    public["project_names_count"] = len(get_project_name_map(session))
    return public


def update_settings(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """
    批量更新配置。
    密钥字段：空字符串或 None 表示不修改；显式传入新值则覆盖。
    """
    now = utcnow()
    current = get_all_settings_map(session)

    for key, value in payload.items():
        if key not in SETTING_KEYS:
            continue
        if value is None:
            continue
        text = str(value).strip() if not isinstance(value, str) else value.strip()
        if key in SECRET_KEYS and text == "":
            continue
        # 防止把脱敏串写回
        if key in SECRET_KEYS and text.startswith(MASK):
            continue

        current[key] = text
        row = session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value=text, updated_at=now))
        else:
            row.value = text
            row.updated_at = now

    session.flush()
    return get_public_config(session)


def build_settings(session: Session, *, require_llm: bool = True) -> Settings:
    """从 DB 构造 Settings；缺省用 DEFAULTS。"""
    raw = get_all_settings_map(session)
    name_map = get_project_name_map(session)

    def req(key: str) -> str:
        value = (raw.get(key) or "").strip()
        if not value:
            raise ValueError(f"缺少必要配置项: {key}，请在管理页或 .env 中设置")
        return value

    llm_api_key = (raw.get("llm_api_key") or "").strip()
    if require_llm and not llm_api_key:
        raise ValueError("缺少必要配置项: llm_api_key，请在管理页或 .env 中设置")

    project_ids_raw = req("project_ids")
    project_ids: list[int] = []
    for part in project_ids_raw.split(","):
        part = part.strip()
        if part:
            project_ids.append(int(part))
    if not project_ids:
        raise ValueError("project_ids 为空，请至少配置一个项目 ID")

    return Settings(
        gitlab_url=req("gitlab_url").rstrip("/"),
        gitlab_token=req("gitlab_token"),
        author_email=req("author_email"),
        project_ids=project_ids,
        llm_api_key=llm_api_key,
        llm_base_url=(raw.get("llm_base_url") or DEFAULTS["llm_base_url"]).rstrip("/"),
        llm_model=raw.get("llm_model") or DEFAULTS["llm_model"],
        llm_timeout=int(raw.get("llm_timeout") or DEFAULTS["llm_timeout"]),
        llm_system_prompt=(
            raw.get("llm_system_prompt")
            or DEFAULTS["llm_system_prompt"]
        ),
        timezone_offset_hours=int(
            raw.get("timezone_offset_hours") or DEFAULTS["timezone_offset_hours"]
        ),
        dingtalk_webhook=(raw.get("dingtalk_webhook") or "").strip(),
        dingtalk_secret=(raw.get("dingtalk_secret") or "").strip(),
        dingtalk_timeout=int(raw.get("dingtalk_timeout") or DEFAULTS["dingtalk_timeout"]),
        project_name_map=name_map,
    )


def list_project_names(session: Session) -> list[dict[str, str]]:
    rows = session.scalars(
        select(ProjectName).order_by(ProjectName.project_key)
    ).all()
    return [
        {"project_key": r.project_key, "display_name": r.display_name}
        for r in rows
    ]


def upsert_project_name(session: Session, project_key: str, display_name: str) -> None:
    key = project_key.strip()
    name = display_name.strip()
    if not key or not name:
        raise ValueError("project_key 与 display_name 均不能为空")
    now = utcnow()
    row = session.get(ProjectName, key)
    if row is None:
        session.add(ProjectName(project_key=key, display_name=name, updated_at=now))
    else:
        row.display_name = name
        row.updated_at = now
    session.flush()


def replace_project_names(session: Session, items: list[dict[str, str]]) -> list[dict[str, str]]:
    existing = session.scalars(select(ProjectName)).all()
    for row in existing:
        session.delete(row)
    session.flush()
    now = utcnow()
    for item in items:
        key = str(item.get("project_key", "")).strip()
        name = str(item.get("display_name", "")).strip()
        if key and name:
            session.add(ProjectName(project_key=key, display_name=name, updated_at=now))
    session.flush()
    return list_project_names(session)


def delete_project_name(session: Session, project_key: str) -> bool:
    row = session.get(ProjectName, project_key)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def get_special_dates(session: Session) -> dict[str, bool]:
    """获取特殊日期：date -> 是否为调休工作日。"""
    rows = session.scalars(select(Holiday)).all()
    return {r.date: r.is_makeup for r in rows}


def upsert_holiday(session: Session, date: str, description: str, is_makeup: bool = False) -> None:
    row = session.get(Holiday, date)
    if row is None:
        session.add(
            Holiday(date=date, description=description, is_makeup=is_makeup)
        )
    else:
        row.description = description
        row.is_makeup = is_makeup
    session.flush()


def delete_holiday(session: Session, date: str) -> bool:
    row = session.get(Holiday, date)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def list_holidays(session: Session) -> list[dict[str, str | bool]]:
    """列出所有节假日。"""
    rows = session.scalars(select(Holiday).order_by(Holiday.date)).all()
    return [
        {
            "date": r.date,
            "description": r.description,
            "is_makeup": r.is_makeup,
        }
        for r in rows
    ]


def save_holidays(
    session: Session,
    items: list[dict[str, str | bool]],
) -> list[dict[str, str | bool]]:
    """保存节假日列表（替换所有）。"""
    existing = session.scalars(select(Holiday)).all()
    for row in existing:
        session.delete(row)
    session.flush()
    for item in items:
        key = item.get("date")
        if isinstance(key, str) and key:
            session.add(
                Holiday(
                    date=key,
                    description=str(item.get("description", "")),
                    is_makeup=bool(item.get("is_makeup", False)),
                )
            )
    session.flush()
    return list_holidays(session)


def save_holidays_for_year(
    session: Session,
    year: int,
    items: list[dict[str, str | bool]],
) -> list[dict[str, str | bool]]:
    """替换指定年份的节假日，保留其他年份。"""
    year_prefix = f"{year:04d}-"
    existing = session.scalars(
        select(Holiday).where(Holiday.date.like(f"{year_prefix}%"))
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()

    for item in items:
        key = item.get("date")
        if not isinstance(key, str) or not key.startswith(year_prefix):
            raise ValueError(f"节假日日期不属于 {year} 年：{key}")
        session.add(
            Holiday(
                date=key,
                description=str(item.get("description", "")),
                is_makeup=bool(item.get("is_makeup", False)),
            )
        )
    session.flush()
    return list_holidays(session)


def delete_holidays_before(session: Session, cutoff_date: str) -> int:
    """删除截止日期之前的特殊日期，返回删除数量。"""
    rows = session.scalars(
        select(Holiday).where(Holiday.date < cutoff_date)
    ).all()
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
