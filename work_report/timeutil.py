"""统一时间：Asia/Shanghai，展示格式 yyyy-MM-dd HH:mm:ss。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# 业务统一时区（东八区）
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
TZ_NAME = "Asia/Shanghai"

# 统一展示 / 落库字符串格式
DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"


def now() -> datetime:
    """当前 Asia/Shanghai 感知时间。"""
    return datetime.now(TZ_SHANGHAI)


def now_naive() -> datetime:
    """
    当前 Asia/Shanghai 墙钟时间（naive）。

    SQLite DateTime 无时区信息，约定库内存储均为上海本地时间。
    """
    return now().replace(tzinfo=None)


def to_shanghai(dt: datetime) -> datetime:
    """转为 Asia/Shanghai 感知时间。naive 视为已是上海本地。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ_SHANGHAI)
    return dt.astimezone(TZ_SHANGHAI)


def format_datetime(value: datetime | str | None, *, empty: str = "") -> str:
    """格式化为 yyyy-MM-dd HH:mm:ss（上海时区）。"""
    if value is None:
        return empty
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return empty
        parsed = parse_datetime(text)
        if parsed is None:
            # 尽力去掉 ISO 的 T / 尾缀，避免前端直接看到 2026-07-28T09:53:39
            normalized = text.replace("T", " ").replace("Z", "")
            if "+" in normalized[10:]:
                normalized = normalized.split("+", 1)[0]
            if normalized.count("-") >= 2 and " " in normalized:
                return normalized[:19]
            return text
        value = parsed
    return to_shanghai(value).strftime(DISPLAY_FORMAT)


def parse_datetime(value: str) -> datetime | None:
    """解析常见时间字符串为感知 datetime（落到上海）。"""
    text = (value or "").strip()
    if not text:
        return None

    # 已是展示格式
    try:
        naive = datetime.strptime(text[:19], DISPLAY_FORMAT)
        # 若原串无时区信息，按上海解释
        if len(text) <= 19 or (text[19:20] not in ("+", "-", "Z") and "T" not in text):
            if "T" not in value and "+" not in text[10:] and not text.endswith("Z"):
                return naive.replace(tzinfo=TZ_SHANGHAI)
    except ValueError:
        pass

    iso = text
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        # 2026-07-28 09:53:39.123
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(text[:26], fmt)
                return dt.replace(tzinfo=TZ_SHANGHAI)
            except ValueError:
                continue
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_SHANGHAI)
    return dt.astimezone(TZ_SHANGHAI)


def format_maybe(value: datetime | str | None) -> str | None:
    """API 序列化：None 保持 None，否则统一展示串。"""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return format_datetime(value)


def tz_from_offset_hours(hours: int = 8) -> timezone | ZoneInfo:
    """兼容配置里的时区偏移；8 固定映射 Asia/Shanghai。"""
    if hours == 8:
        return TZ_SHANGHAI
    return timezone(timedelta(hours=hours))
