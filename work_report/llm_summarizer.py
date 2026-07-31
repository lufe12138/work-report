"""LLM 周报归纳模块（OpenAI 兼容接口）。"""

from __future__ import annotations

import logging
import re

from openai import OpenAI

from work_report.config import Settings
from work_report.default_prompts import DEFAULT_WEEKLY_REPORT_PROMPT
from work_report.gitlab_fetcher import FetchResult

logger = logging.getLogger(__name__)

# LLM 配置页测活提示词
PING_PROMPT = "计算2+3等于多少"

# 匹配：一、任意标题（project_key） 或 一、project_key
_SECTION_TITLE_RE = re.compile(
    r"^([一二三四五六七八九十百千]+、)"  # 中文序号
    r"(.*?)"  # 标题中文部分（可空）
    r"（([a-zA-Z0-9_.\-]+)）"  # （gitlab_project_name）
    r"\s*$",
    re.MULTILINE,
)
_SECTION_TITLE_EN_ONLY_RE = re.compile(
    r"^([一二三四五六七八九十百千]+、)"
    r"([a-zA-Z0-9_.\-]+)"
    r"\s*$",
    re.MULTILINE,
)

def _date_only(value: str) -> str:
    """从 '2026-07-27 00:00:00' / ISO 中取出 YYYY-MM-DD。"""
    value = (value or "").strip()
    if not value:
        return ""
    return value[:10]


def format_report_header(week_start: str, week_end: str) -> str:
    """【周报】起始日期 ~ 结束日期"""
    start = _date_only(week_start)
    end = _date_only(week_end)
    if start and end:
        if start == end:
            return f"【周报】{start}"
        return f"【周报】{start} ~ {end}"
    if end:
        return f"【周报】{end}"
    if start:
        return f"【周报】{start}"
    return "【周报】"


def normalize_project_titles(report: str, name_map: dict[str, str]) -> str:
    """
    用 project_names.json 强制校正一级标题中文名。

    例如 LLM 写成「后端服务（example_backend）」
    会改回「示例后端服务（example_backend）」。
    """
    if not report or not name_map:
        return report

    def repl_full(match: re.Match[str]) -> str:
        prefix, project_key = match.group(1), match.group(3)
        zh = name_map.get(project_key, "").strip()
        if zh:
            fixed = f"{prefix}{zh}（{project_key}）"
            if match.group(0) != fixed:
                logger.info("校正项目标题: %s -> %s", match.group(0), fixed)
            return fixed
        # 无映射则去掉胡编中文，只保留英文名
        return f"{prefix}{project_key}"

    def repl_en(match: re.Match[str]) -> str:
        prefix, project_key = match.group(1), match.group(2)
        zh = name_map.get(project_key, "").strip()
        if zh:
            fixed = f"{prefix}{zh}（{project_key}）"
            logger.info("补全项目中文名: %s -> %s", match.group(0), fixed)
            return fixed
        return match.group(0)

    text = _SECTION_TITLE_RE.sub(repl_full, report)
    text = _SECTION_TITLE_EN_ONLY_RE.sub(repl_en, text)
    return text


def ensure_report_header(report: str, week_start: str, week_end: str) -> str:
    """确保正文开头带【周报】起止日期；若已有则替换为标准格式。"""
    header = format_report_header(week_start, week_end)
    body = (report or "").strip()
    if not body:
        return header

    # 去掉 LLM 可能自带的【周报】行
    lines = body.splitlines()
    if lines and lines[0].strip().startswith("【周报】"):
        rest = "\n".join(lines[1:]).lstrip()
        return f"{header}\n\n{rest}" if rest else header
    return f"{header}\n\n{body}"


class LLMSummarizer:
    """调用 OpenAI 兼容 API 将提交记录归纳为周报。"""

    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout,
        )

    def build_user_prompt(self, fetch_result: FetchResult) -> str:
        """构造用户侧提示词。"""
        body = fetch_result.to_prompt_text()
        extra = ""
        if self.settings.project_name_map:
            extra = (
                "\n\n再次强调：一级标题中的业务中文名必须严格使用上文「项目中文名映射」，"
                "不得改成其他叫法。"
            )
        return (
            "请根据以下本周 GitLab 提交记录生成周报。\n\n"
            f"{body}{extra}"
        )

    def postprocess(self, content: str, fetch_result: FetchResult) -> str:
        """校正项目中文名，并加上起止日期标题。"""
        text = normalize_project_titles(content, self.settings.project_name_map)
        text = ensure_report_header(
            text,
            fetch_result.week_start,
            fetch_result.week_end,
        )
        return text

    def ping(self, prompt: str = PING_PROMPT) -> str:
        """连通性测活：发一条短提示词，返回模型原文回复。"""
        logger.info(
            "LLM 测活: model=%s, base_url=%s, prompt=%s",
            self.settings.llm_model,
            self.settings.llm_base_url,
            prompt,
        )
        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=64,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("LLM 返回空内容")
        return content

    def summarize(self, fetch_result: FetchResult) -> str:
        """根据提交结果生成周报正文。"""
        if fetch_result.total_commits == 0:
            logger.info("本周无提交，跳过 LLM 调用")
            return ensure_report_header(
                "本周暂无提交记录",
                fetch_result.week_start,
                fetch_result.week_end,
            )

        user_prompt = self.build_user_prompt(fetch_result)
        logger.info(
            "调用 LLM 生成周报: model=%s, base_url=%s, commits=%s",
            self.settings.llm_model,
            self.settings.llm_base_url,
            fetch_result.total_commits,
        )

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        self.settings.llm_system_prompt.strip()
                        or DEFAULT_WEEKLY_REPORT_PROMPT
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("LLM 返回空内容")
        return self.postprocess(content, fetch_result)
