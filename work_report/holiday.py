"""
节假日 / 工作日判断。

判定规则（与原 check_holiday 一致）：
  今天是工作日 AND 明天是非工作日 → 放假前最后一个工作日

非工作日：
  1. 法定节假日（HOLIDAYS）
  2. 周末，且不在调休上班日（MAKEUP_WORKDAYS）

数据来源：国务院办公厅关于 2026 年部分节假日安排的通知（国办发明电〔2025〕7号）
每年节前更新 HOLIDAYS / MAKEUP_WORKDAYS 即可，无需联网。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ============ 2026 年法定节假日（放假日） ============
HOLIDAYS: set[str] = {
    # 元旦：1月1日-3日
    "2026-01-01",
    "2026-01-02",
    "2026-01-03",
    # 春节：2月15日-23日
    "2026-02-15",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-02-19",
    "2026-02-20",
    "2026-02-21",
    "2026-02-22",
    "2026-02-23",
    # 清明节：4月4日-6日
    "2026-04-04",
    "2026-04-05",
    "2026-04-06",
    # 劳动节：5月1日-5日
    "2026-05-01",
    "2026-05-02",
    "2026-05-03",
    "2026-05-04",
    "2026-05-05",
    # 端午节：6月19日-21日
    "2026-06-19",
    "2026-06-20",
    "2026-06-21",
    # 中秋节：9月25日-27日
    "2026-09-25",
    "2026-09-26",
    "2026-09-27",
    # 国庆节：10月1日-7日
    "2026-10-01",
    "2026-10-02",
    "2026-10-03",
    "2026-10-04",
    "2026-10-05",
    "2026-10-06",
    "2026-10-07",
}

# ============ 2026 年调休上班日（周末但上班） ============
MAKEUP_WORKDAYS: set[str] = {
    "2026-01-04",  # 元旦调休（周日）
    "2026-02-14",  # 春节调休（周六）
    "2026-02-28",  # 春节调休（周六）
    "2026-05-09",  # 劳动节调休（周六）
    "2026-09-20",  # 国庆调休（周日）
    "2026-10-10",  # 国庆调休（周六）
}

WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _to_date(value: date | datetime | str | None, tz: timezone) -> date:
    if value is None:
        return datetime.now(tz).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def is_workday(
    day: date | datetime | str,
    *,
    tz_offset_hours: int = 8,
    workday_overrides: Mapping[str, bool] | None = None,
) -> bool:
    """判断指定日期是否为工作日。"""
    tz = timezone(timedelta(hours=tz_offset_hours))
    d = _to_date(day, tz)
    date_str = d.isoformat()

    if workday_overrides is not None:
        if date_str in workday_overrides:
            return workday_overrides[date_str]
    else:
        if date_str in MAKEUP_WORKDAYS:
            return True
        if date_str in HOLIDAYS:
            return False
    return d.weekday() < 5


@dataclass(frozen=True)
class HolidayCheckResult:
    """放假前最后一个工作日判定结果。"""

    today: str
    tomorrow: str
    today_weekday: str
    tomorrow_weekday: str
    today_is_workday: bool
    tomorrow_is_workday: bool
    is_last_workday_before_holiday: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "today": self.today,
            "tomorrow": self.tomorrow,
            "today_weekday": self.today_weekday,
            "tomorrow_weekday": self.tomorrow_weekday,
            "today_is_workday": self.today_is_workday,
            "tomorrow_is_workday": self.tomorrow_is_workday,
            "is_last_workday_before_holiday": self.is_last_workday_before_holiday,
            "reason": self.reason,
        }


def check_last_workday_before_holiday(
    day: date | datetime | str | None = None,
    *,
    tz_offset_hours: int = 8,
    workday_overrides: Mapping[str, bool] | None = None,
) -> HolidayCheckResult:
    """
    判断「今天」是否为放假前最后一个工作日。

    条件：今天是工作日，且明天不是工作日（周末/法定假/连休）。
    """
    tz = timezone(timedelta(hours=tz_offset_hours))
    today = _to_date(day, tz)
    tomorrow = today + timedelta(days=1)

    today_work = is_workday(
        today,
        tz_offset_hours=tz_offset_hours,
        workday_overrides=workday_overrides,
    )
    tomorrow_work = is_workday(
        tomorrow,
        tz_offset_hours=tz_offset_hours,
        workday_overrides=workday_overrides,
    )
    is_last = today_work and not tomorrow_work

    if is_last:
        reason = f"今天是工作日，明天({tomorrow.isoformat()})非工作日，将生成周报"
    elif not today_work:
        reason = "今天不是工作日，跳过"
    else:
        reason = f"明天({tomorrow.isoformat()})仍是工作日，跳过"

    return HolidayCheckResult(
        today=today.isoformat(),
        tomorrow=tomorrow.isoformat(),
        today_weekday=WEEKDAY_NAMES[today.weekday()],
        tomorrow_weekday=WEEKDAY_NAMES[tomorrow.weekday()],
        today_is_workday=today_work,
        tomorrow_is_workday=tomorrow_work,
        is_last_workday_before_holiday=is_last,
        reason=reason,
    )
