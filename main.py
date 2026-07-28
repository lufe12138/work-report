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
from work_report.db.session import init_db, session_scope
from work_report.dingtalk_sender import DingTalkSender
from work_report.holiday import check_last_workday_before_holiday
from work_report.pipeline import RunOptions, run_pipeline
from work_report.services import settings_service

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
        help="指定 .env 文件路径（默认使用项目根目录 .env；首次会 seed 到 SQLite）",
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
    today = datetime.now().strftime("%Y-%m-%d")
    return ROOT_DIR / "output" / f"weekly-report-{today}.txt"


def run_holiday_check(tz_offset_hours: int = 8) -> int:
    result = check_last_workday_before_holiday(tz_offset_hours=tz_offset_hours)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    logger.info("%s", result.reason)
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    setup_logging(args.verbose)

    # 初始化 DB（空库时从 .env seed）
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("初始化数据库失败（将仅影响落库）: %s", exc)

    if args.check_holiday:
        try:
            with session_scope() as session:
                raw = settings_service.get_all_settings_map(session)
                tz = int(raw.get("timezone_offset_hours") or 8)
        except Exception:  # noqa: BLE001
            try:
                settings = load_settings(args.env, require_llm=False)
                tz = settings.timezone_offset_hours
            except Exception:  # noqa: BLE001
                tz = 8
        return run_holiday_check(tz)

    if args.test_dingtalk:
        try:
            with session_scope() as session:
                settings = settings_service.build_settings(session, require_llm=False)
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

    # 发送策略：默认发（若已配置）；--no-dingtalk 禁用；--send-dingtalk 仅强制要求已配置
    send_dingtalk = not args.no_dingtalk
    if args.send_dingtalk:
        send_dingtalk = True

    trigger = "schedule" if args.if_last_workday else "cli"
    options = RunOptions(
        skip_llm=args.skip_llm,
        send_dingtalk=send_dingtalk,
        if_last_workday=args.if_last_workday,
        trigger=trigger,
    )

    try:
        result = run_pipeline(options)
    except Exception as exc:  # noqa: BLE001
        logger.error("执行失败: %s", exc)
        return 2

    logger.info(
        "运行完成: run_id=%s status=%s commits=%s",
        result.run_id,
        result.status,
        result.total_commits,
    )

    if result.status == "skipped":
        logger.info("已跳过: %s", result.error_message)
        return 0

    if result.status == "failed":
        logger.error("任务失败: %s", result.error_message)
        return 2

    report_text = result.report_text
    if args.json:
        payload = {
            "run_id": result.run_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "week_start": result.week_start,
            "week_end": result.week_end,
            "total_commits": result.total_commits,
            "status": result.status,
            "dingtalk_sent": result.dingtalk_sent,
            "report": report_text,
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        output = report_text

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

    return 0


if __name__ == "__main__":
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    raise SystemExit(main())
