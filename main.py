#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""周报生成入口：节假日判断 → 拉取 GitLab 提交 → LLM 归纳 → 输出 / 钉钉发送。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from work_report.config import ROOT_DIR, load_settings
from work_report.dingtalk_sender import DingTalkSender
from work_report.gitlab_fetcher import GitLabFetcher
from work_report.holiday import check_last_workday_before_holiday
from work_report.llm_summarizer import LLMSummarizer

logger = logging.getLogger("main")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 GitLab 提交生成周报")
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="指定 .env 文件路径（默认使用项目根目录 .env）",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="将周报写入文件；默认打印到 stdout",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出（含元数据与周报正文）",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="只拉取提交，不调用 LLM（输出原始提交文本）",
    )
    parser.add_argument(
        "--if-last-workday",
        action="store_true",
        help="仅在「放假前最后一个工作日」时生成周报（定时任务推荐开启）",
    )
    parser.add_argument(
        "--check-holiday",
        action="store_true",
        help="只输出节假日判断结果（JSON），不拉取提交",
    )
    parser.add_argument(
        "--send-dingtalk",
        action="store_true",
        help="强制发送钉钉（需配置 DINGTALK_WEBHOOK）",
    )
    parser.add_argument(
        "--no-dingtalk",
        action="store_true",
        help="不发送钉钉（即使已配置 Webhook）",
    )
    parser.add_argument(
        "--test-dingtalk",
        action="store_true",
        help="仅发送一条钉钉测试消息后退出",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出调试日志",
    )
    return parser.parse_args()


def _default_output_path() -> Path:
    """定时任务默认输出路径：output/weekly-report-YYYY-MM-DD.txt"""
    today = datetime.now().strftime("%Y-%m-%d")
    return ROOT_DIR / "output" / f"weekly-report-{today}.txt"


def run_holiday_check(tz_offset_hours: int = 8) -> int:
    """仅检查节假日，打印 JSON。"""
    result = check_last_workday_before_holiday(tz_offset_hours=tz_offset_hours)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    logger.info("%s", result.reason)
    return 0


def maybe_send_dingtalk(
    settings,
    report_text: str,
    *,
    force: bool,
    disabled: bool,
    week_start: str | None = None,
    week_end: str | None = None,
) -> None:
    """按配置/参数决定是否发送钉钉。"""
    if disabled:
        logger.info("已指定 --no-dingtalk，跳过钉钉发送")
        return

    sender = DingTalkSender(settings)
    if not sender.enabled:
        if force:
            raise RuntimeError("已指定 --send-dingtalk，但未配置 DINGTALK_WEBHOOK")
        logger.info("未配置 DINGTALK_WEBHOOK，跳过钉钉发送")
        return

    # 默认：配置了 webhook 就发；--send-dingtalk 仅用于强制校验配置存在
    sender.send_weekly_report(
        report_text,
        week_start=week_start,
        week_end=week_end,
    )


def main() -> int:
    # Windows 控制台 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    setup_logging(args.verbose)

    # 仅节假日检查：不依赖 GitLab / LLM 配置
    if args.check_holiday:
        try:
            settings = load_settings(args.env, require_llm=False)
            tz = settings.timezone_offset_hours
        except Exception:  # noqa: BLE001
            tz = 8
        return run_holiday_check(tz)

    # 钉钉连通性测试
    if args.test_dingtalk:
        try:
            settings = load_settings(args.env, require_llm=False)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1
        try:
            sender = DingTalkSender(settings)
            if not sender.enabled:
                logger.error("未配置 DINGTALK_WEBHOOK")
                return 1
            sender.send_text(
                "work-report 钉钉机器人连通性测试成功。",
                title="【周报】测试消息",
            )
            print("钉钉测试消息已发送")
            return 0
        except Exception as exc:  # noqa: BLE001
            logger.error("钉钉测试失败: %s", exc)
            return 3

    try:
        settings = load_settings(args.env, require_llm=not args.skip_llm)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    # 定时任务入口：先判断是否放假前最后一个工作日
    if args.if_last_workday:
        holiday = check_last_workday_before_holiday(
            tz_offset_hours=settings.timezone_offset_hours
        )
        logger.info(
            "节假日判断: 今天 %s(%s) 工作日=%s, 明天 %s(%s) 工作日=%s → %s",
            holiday.today,
            holiday.today_weekday,
            holiday.today_is_workday,
            holiday.tomorrow,
            holiday.tomorrow_weekday,
            holiday.tomorrow_is_workday,
            holiday.reason,
        )
        if not holiday.is_last_workday_before_holiday:
            logger.info("跳过周报生成")
            return 0

    fetcher = GitLabFetcher(settings)
    fetch_result = fetcher.fetch_week_commits()

    if fetch_result.errors:
        for err in fetch_result.errors:
            logger.warning("拉取时出现错误: %s", err)

    logger.info(
        "拉取完成: 共 %s 条提交，涉及 %s 个项目",
        fetch_result.total_commits,
        len(fetch_result.projects),
    )

    if args.skip_llm:
        report_text = fetch_result.to_prompt_text()
    else:
        try:
            summarizer = LLMSummarizer(settings)
            report_text = summarizer.summarize(fetch_result)
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM 生成周报失败: %s", exc)
            return 2

    if args.json:
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "week_start": fetch_result.week_start,
            "week_end": fetch_result.week_end,
            "total_commits": fetch_result.total_commits,
            "projects": fetch_result.projects,
            "errors": fetch_result.errors,
            "report": report_text,
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2)
        dingtalk_body = report_text  # 钉钉仍发纯文本周报
    else:
        output = report_text
        dingtalk_body = report_text

    # 定时任务未指定 -o 时，自动落到 output/
    out_path: Path | None
    if args.output:
        out_path = Path(args.output)
    elif args.if_last_workday:
        out_path = _default_output_path()
    else:
        out_path = None

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
        logger.info("周报已写入: %s", out_path.resolve())
        if args.if_last_workday:
            print(output)
    else:
        print(output)

    try:
        maybe_send_dingtalk(
            settings,
            dingtalk_body,
            force=args.send_dingtalk,
            disabled=args.no_dingtalk,
            week_start=fetch_result.week_start,
            week_end=fetch_result.week_end,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("钉钉发送失败: %s", exc)
        return 3

    return 0


if __name__ == "__main__":
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    raise SystemExit(main())
