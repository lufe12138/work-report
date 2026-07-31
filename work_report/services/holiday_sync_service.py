"""从国务院官方页面抓取并解析节假日安排。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlparse

import requests

POLICY_SEARCH_URL = "https://sousuo.www.gov.cn/search-gov/data"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
)

_SECTION_PATTERN = re.compile(
    r"[一二三四五六七八九十]+、(?P<name>[^：:。]+)[：:]"
    r"(?P<body>.*?)"
    r"(?=(?:[一二三四五六七八九十]+、[^：:。]+[：:])|鼓励|节假日期间|国务院办公厅)"
)
_DATE_PATTERN = re.compile(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
_RANGE_PATTERN = re.compile(
    r"(?P<start_month>\d{1,2})月(?P<start_day>\d{1,2})日"
    r".*?至"
    r"(?:(?P<end_month>\d{1,2})月)?(?P<end_day>\d{1,2})日"
    r".*?放假"
)
_SINGLE_DAY_PATTERN = re.compile(
    r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日.*?放假"
)


class OfficialHolidaySyncError(RuntimeError):
    """官方节假日页面抓取或解析失败。"""


class OfficialHolidayNotFoundError(OfficialHolidaySyncError):
    """指定年份的官方节假日通知尚未发布或未被检索到。"""


@dataclass(frozen=True)
class OfficialHolidaySchedule:
    """从官方页面解析出的节假日安排。"""

    year: int
    source_url: str
    items: list[dict[str, str | bool]]


def _html_to_text(content: str) -> str:
    without_scripts = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_tags = re.sub(r"<[^>]+>", "", without_scripts)
    return re.sub(r"\s+", "", html.unescape(without_tags))


def _parse_date(year: int, month: str, day: str) -> date:
    try:
        return date(year, int(month), int(day))
    except ValueError as exc:
        raise OfficialHolidaySyncError(
            f"官方页面包含无效日期：{year}-{month}-{day}"
        ) from exc


def _add_item(
    items: dict[str, dict[str, str | bool]],
    item_date: date,
    description: str,
    *,
    is_makeup: bool,
) -> None:
    key = item_date.isoformat()
    existing = items.get(key)
    if existing is not None and bool(existing["is_makeup"]) != is_makeup:
        raise OfficialHolidaySyncError(f"官方页面日期类型冲突：{key}")
    items[key] = {
        "date": key,
        "description": description,
        "is_makeup": is_makeup,
    }


def parse_official_holiday_schedule(
    content: str,
    *,
    source_url: str = "",
) -> OfficialHolidaySchedule:
    """解析国务院节假日通知 HTML。"""
    text = _html_to_text(content)
    year_match = re.search(r"关于(?P<year>\d{4})年部分节假日安排的通知", text)
    if year_match is None:
        raise OfficialHolidaySyncError("未识别到官方通知年份")
    year = int(year_match.group("year"))

    sections = list(_SECTION_PATTERN.finditer(text))
    if len(sections) < 6:
        raise OfficialHolidaySyncError("官方通知中的节假日分组不完整")

    items: dict[str, dict[str, str | bool]] = {}
    for section in sections:
        name = section.group("name").strip()
        body = section.group("body")
        sentences = [sentence for sentence in body.split("。") if sentence]
        holiday_sentence = next(
            (sentence for sentence in sentences if "放假" in sentence),
            None,
        )
        if holiday_sentence is None:
            raise OfficialHolidaySyncError(f"未识别到{name}的放假日期")

        range_match = _RANGE_PATTERN.search(holiday_sentence)
        if range_match is not None:
            start = _parse_date(
                year,
                range_match.group("start_month"),
                range_match.group("start_day"),
            )
            end_month = (
                range_match.group("end_month")
                or range_match.group("start_month")
            )
            end = _parse_date(year, end_month, range_match.group("end_day"))
            if end < start or (end - start).days > 31:
                raise OfficialHolidaySyncError(f"{name}的放假日期范围异常")
            current = start
            while current <= end:
                _add_item(items, current, name, is_makeup=False)
                current += timedelta(days=1)
        else:
            single_match = _SINGLE_DAY_PATTERN.search(holiday_sentence)
            if single_match is None:
                raise OfficialHolidaySyncError(f"未识别到{name}的放假日期")
            holiday_date = _parse_date(
                year,
                single_match.group("month"),
                single_match.group("day"),
            )
            _add_item(items, holiday_date, name, is_makeup=False)

        for sentence in sentences:
            if "上班" not in sentence:
                continue
            for match in _DATE_PATTERN.finditer(sentence):
                makeup_date = _parse_date(
                    year,
                    match.group("month"),
                    match.group("day"),
                )
                _add_item(
                    items,
                    makeup_date,
                    f"{name}调休",
                    is_makeup=True,
                )

    if not items:
        raise OfficialHolidaySyncError("官方通知未解析出任何节假日")
    return OfficialHolidaySchedule(
        year=year,
        source_url=source_url,
        items=[items[key] for key in sorted(items)],
    )


def _holiday_notice_title(year: int) -> str:
    return f"国务院办公厅关于{year}年部分节假日安排的通知"


def _validate_official_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.gov.cn":
        raise OfficialHolidaySyncError("政策文件库返回了非国务院官网地址")
    return url


def discover_official_holiday_url(
    year: int,
    *,
    timeout_seconds: int = 15,
) -> str:
    """从国务院政策文件库查找指定年份的节假日通知。"""
    title = _holiday_notice_title(year)
    try:
        response = requests.get(
            POLICY_SEARCH_URL,
            params={
                "t": "zhengcelibrary",
                "q": title,
                "sort": "score",
                "searchfield": "title:content:summary",
                "p": 1,
                "n": 10,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise OfficialHolidaySyncError(
            f"访问国务院政策文件库失败：{exc}"
        ) from exc

    category_map = (payload.get("searchVO") or {}).get("catMap") or {}
    for category_name in ("gongwen", "gongbao"):
        category = category_map.get(category_name) or {}
        for result in category.get("listVO") or []:
            result_title = _html_to_text(str(result.get("title") or ""))
            if result_title != title:
                continue
            source_url = str(result.get("url") or "")
            if source_url:
                return _validate_official_url(source_url)

    raise OfficialHolidayNotFoundError(
        f"国务院尚未发布 {year} 年节假日安排，或政策文件库暂未收录"
    )


def fetch_official_holiday_schedule(
    year: int,
    *,
    timeout_seconds: int = 15,
) -> OfficialHolidaySchedule:
    """查找、抓取并解析指定年份的国务院节假日通知。"""
    source_url = discover_official_holiday_url(
        year,
        timeout_seconds=timeout_seconds,
    )
    try:
        response = requests.get(
            source_url,
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OfficialHolidaySyncError(
            f"访问国务院官方页面失败：{exc}"
        ) from exc

    if response.encoding is None or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    final_url = _validate_official_url(response.url)
    schedule = parse_official_holiday_schedule(
        response.text,
        source_url=final_url,
    )
    if schedule.year != year:
        raise OfficialHolidaySyncError(
            f"官方通知年份与请求年份不一致：请求 {year} 年，解析到 "
            f"{schedule.year} 年"
        )
    return schedule
