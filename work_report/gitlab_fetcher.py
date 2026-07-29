"""GitLab 提交记录获取模块。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import requests

from work_report.config import Settings
from work_report.timeutil import format_datetime, tz_from_offset_hours

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    """单条提交摘要。"""

    short_id: str
    title: str
    message: str
    author_name: str
    author_email: str
    created_at: str
    project_id: int
    project_name: str

    @property
    def date(self) -> str:
        return self.created_at[:10] if self.created_at else ""


@dataclass
class FetchResult:
    """本周提交拉取结果。"""

    week_start: str
    week_end: str
    commits: list[CommitInfo] = field(default_factory=list)
    # project_name -> commits
    by_project: dict[str, list[CommitInfo]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    # GitLab 项目名 -> 业务中文名
    project_name_map: dict[str, str] = field(default_factory=dict)

    @property
    def total_commits(self) -> int:
        return len(self.commits)

    @property
    def projects(self) -> list[str]:
        return [name for name, items in self.by_project.items() if items]

    def display_name(self, project_name: str) -> str:
        zh = self.project_name_map.get(project_name, "").strip()
        if zh:
            return f"{zh}（{project_name}）"
        return project_name

    def to_prompt_text(self) -> str:
        """将提交整理为供 LLM 使用的纯文本。"""
        if not self.commits:
            return "本周暂无提交记录。"

        display_projects = [self.display_name(p) for p in self.projects]
        lines: list[str] = [
            f"时间范围: {self.week_start} ~ {self.week_end}",
            f"提交总数: {self.total_commits}",
            f"涉及项目: {', '.join(display_projects)}",
            "",
        ]

        # 显式给出映射表，要求 LLM 原样使用
        if self.project_name_map:
            lines.append("【项目中文名映射（必须原样使用，禁止改写）】")
            for pname in self.projects:
                zh = self.project_name_map.get(pname, "").strip()
                if zh:
                    lines.append(f"  {pname} => {zh}")
                else:
                    lines.append(f"  {pname} => （无映射，标题仅用英文项目名）")
            lines.append("")

        for project_name, commits in self.by_project.items():
            if not commits:
                continue
            lines.append(f"【项目】{self.display_name(project_name)}")
            by_date: dict[str, list[CommitInfo]] = {}
            for c in commits:
                by_date.setdefault(c.date, []).append(c)
            for date in sorted(by_date.keys(), reverse=True):
                lines.append(f"  {date}")
                for c in by_date[date]:
                    title = c.title.strip() or c.message.splitlines()[0].strip()
                    lines.append(f"  - {title} ({c.short_id})")
            lines.append("")

        return "\n".join(lines).rstrip()


class GitLabFetcher:
    """从 GitLab API 拉取指定作者的本周提交。"""

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.update({"PRIVATE-TOKEN": settings.gitlab_token})
        # 业务展示与「本周」边界统一按配置偏移；默认 8 = Asia/Shanghai
        self.tz = tz_from_offset_hours(settings.timezone_offset_hours)

    def _url(self, path: str) -> str:
        return f"{self.settings.gitlab_url}/api/v4{path}"

    def get_project_name(self, project_id: int) -> str:
        """获取项目名称，失败时回退为 项目-{id}。"""
        try:
            resp = self.session.get(
                self._url(f"/projects/{project_id}"),
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("name", f"项目-{project_id}")
        except Exception as exc:  # noqa: BLE001 - 单个项目失败不阻断整体
            logger.warning("获取项目 %s 名称失败: %s", project_id, exc)
            return f"项目-{project_id}"

    def fetch_project_commits(
        self,
        project_id: int,
        project_name: str,
        since: str,
        until: str,
    ) -> list[CommitInfo]:
        """获取单个项目在时间范围内、属于当前作者的提交。"""
        url = self._url(f"/projects/{project_id}/repository/commits")
        params = {
            "since": since,
            "until": until,
            "per_page": 100,
            "all": "true",
        }
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            raw_commits: list[dict[str, Any]] = resp.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning("项目 %s (%s) 请求失败: HTTP %s", project_name, project_id, status)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("项目 %s (%s) 请求异常: %s", project_name, project_id, exc)
            raise

        author = self.settings.author_email.lower()
        result: list[CommitInfo] = []
        for c in raw_commits:
            email = (c.get("author_email") or "").lower()
            name = (c.get("author_name") or "").lower()
            if author not in email and author not in name:
                continue
            raw_created = c.get("created_at", "") or ""
            result.append(
                CommitInfo(
                    short_id=c.get("short_id", ""),
                    title=(c.get("title") or "").strip(),
                    message=(c.get("message") or "").strip(),
                    author_name=c.get("author_name", ""),
                    author_email=c.get("author_email", ""),
                    created_at=format_datetime(raw_created) or raw_created,
                    project_id=project_id,
                    project_name=project_name,
                )
            )
        return result

    @staticmethod
    def _fmt_display(dt: datetime) -> str:
        """日志/展示用时间：2026-07-27 17:37:42（上海）"""
        return format_datetime(dt)

    def current_week_range(
        self, now: datetime | None = None
    ) -> tuple[str, str, datetime, datetime]:
        """
        返回本周一 00:00 到当前时间（业务时区，默认 Asia/Shanghai）。

        返回:
            (since_iso, until_iso, week_start_dt, now_dt)
            ISO 字符串供 GitLab API 使用。
        """
        now = now or datetime.now(self.tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.tz)
        else:
            now = now.astimezone(self.tz)
        # weekday: Monday=0 ... Sunday=6
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return week_start.isoformat(), now.isoformat(), week_start, now

    def fetch_week_commits(self, now: datetime | None = None) -> FetchResult:
        """拉取配置中所有项目的本周提交（本周一 00:00 至今）。"""
        since_iso, until_iso, week_start_dt, now_dt = self.current_week_range(now)
        start_display = self._fmt_display(week_start_dt)
        end_display = self._fmt_display(now_dt)
        weekday_names = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
        logger.info(
            "查询时间范围: %s ~ %s（本%s 00:00 至今，共 %s 天）",
            start_display,
            end_display,
            weekday_names[week_start_dt.weekday()],
            (now_dt.date() - week_start_dt.date()).days + 1,
        )

        by_project: dict[str, list[CommitInfo]] = {}
        all_commits: list[CommitInfo] = []
        errors: list[str] = []

        for pid in self.settings.project_ids:
            project_name = self.get_project_name(pid)
            logger.info("正在获取项目 [%s] (ID=%s) 的提交...", project_name, pid)
            try:
                commits = self.fetch_project_commits(
                    pid, project_name, since_iso, until_iso
                )
                by_project[project_name] = commits
                all_commits.extend(commits)
                logger.info("  找到 %s 条提交", len(commits))
            except Exception as exc:  # noqa: BLE001
                msg = f"项目 {project_name}({pid}): {exc}"
                errors.append(msg)
                by_project[project_name] = []

        # 按时间倒序
        all_commits.sort(key=lambda c: c.created_at, reverse=True)

        return FetchResult(
            week_start=start_display,
            week_end=end_display,
            commits=all_commits,
            by_project=by_project,
            errors=errors,
            project_name_map=dict(self.settings.project_name_map),
        )
