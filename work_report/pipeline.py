"""统一周报执行流水线（CLI / Web 共用），并写入 SQLite 运行记录。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from work_report.db.models import Run, RunCommit, RunLog, utcnow
from work_report.db.session import get_session_factory, init_db
from work_report.dingtalk_sender import DingTalkSender
from work_report.gitlab_fetcher import GitLabFetcher
from work_report.holiday import check_last_workday_before_holiday
from work_report.llm_summarizer import LLMSummarizer
from work_report.services.settings_service import build_settings

logger = logging.getLogger(__name__)


@dataclass
class RunOptions:
    skip_llm: bool = False
    send_dingtalk: bool = True
    if_last_workday: bool = False
    trigger: str = "cli"

    def to_dict(self) -> dict[str, Any]:
        return {
            "skip_llm": self.skip_llm,
            "send_dingtalk": self.send_dingtalk,
            "if_last_workday": self.if_last_workday,
            "trigger": self.trigger,
        }


@dataclass
class PipelineResult:
    run_id: int
    status: str
    report_text: str = ""
    week_start: str = ""
    week_end: str = ""
    total_commits: int = 0
    error_message: str | None = None
    dingtalk_sent: bool = False


def _add_log(session: Session, run_id: int, level: str, message: str) -> None:
    session.add(
        RunLog(run_id=run_id, level=level, message=message, created_at=utcnow())
    )
    session.flush()
    log_fn = logger.info if level == "INFO" else (
        logger.warning if level == "WARNING" else logger.error
    )
    log_fn("[run %s] %s", run_id, message)


def execute_run(run_id: int) -> PipelineResult:
    """执行已创建的 runs 记录（status 从 pending/running 推进）。"""
    factory = get_session_factory()
    session = factory()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise RuntimeError(f"run {run_id} 不存在")

        try:
            options = json.loads(run.options_json or "{}")
        except json.JSONDecodeError:
            options = {}

        skip_llm = bool(options.get("skip_llm", False))
        send_dingtalk = bool(options.get("send_dingtalk", True))
        if_last_workday = bool(options.get("if_last_workday", False))

        run.status = "running"
        run.started_at = utcnow()
        session.commit()

        _add_log(session, run_id, "INFO", "任务开始执行")
        session.commit()

        settings = build_settings(session, require_llm=not skip_llm)

        if if_last_workday:
            holiday = check_last_workday_before_holiday(
                tz_offset_hours=settings.timezone_offset_hours
            )
            reason = holiday.reason
            run.holiday_reason = reason
            _add_log(
                session,
                run_id,
                "INFO",
                f"节假日判断: 今天={holiday.today} 工作日={holiday.today_is_workday}, "
                f"明天={holiday.tomorrow} 工作日={holiday.tomorrow_is_workday} → {reason}",
            )
            session.commit()
            if not holiday.is_last_workday_before_holiday:
                run.status = "skipped"
                run.finished_at = utcnow()
                run.error_message = None
                _add_log(session, run_id, "INFO", "非放假前最后工作日，跳过生成")
                session.commit()
                return PipelineResult(
                    run_id=run_id,
                    status="skipped",
                    error_message=reason,
                )

        _add_log(session, run_id, "INFO", "开始拉取 GitLab 提交")
        session.commit()

        fetcher = GitLabFetcher(settings)
        fetch_result = fetcher.fetch_week_commits()

        run.week_start = fetch_result.week_start
        run.week_end = fetch_result.week_end
        run.total_commits = fetch_result.total_commits
        run.project_count = len(fetch_result.projects)

        for err in fetch_result.errors:
            _add_log(session, run_id, "WARNING", f"拉取错误: {err}")

        # 清空旧 commits（一般没有）
        for c in list(run.commits):
            session.delete(c)
        session.flush()

        for commit in fetch_result.commits:
            session.add(
                RunCommit(
                    run_id=run_id,
                    project_id=commit.project_id,
                    project_name=commit.project_name,
                    short_id=commit.short_id,
                    title=commit.title,
                    message=commit.message,
                    author_name=commit.author_name,
                    author_email=commit.author_email,
                    commit_created_at=commit.created_at,
                )
            )

        _add_log(
            session,
            run_id,
            "INFO",
            f"拉取完成: {fetch_result.total_commits} 条提交，"
            f"{len(fetch_result.projects)} 个项目",
        )
        session.commit()

        if skip_llm:
            report_text = fetch_result.to_prompt_text()
            _add_log(session, run_id, "INFO", "已跳过 LLM，使用原始提交文本")
        else:
            _add_log(session, run_id, "INFO", f"调用 LLM: model={settings.llm_model}")
            session.commit()
            summarizer = LLMSummarizer(settings)
            report_text = summarizer.summarize(fetch_result)
            _add_log(session, run_id, "INFO", "LLM 周报生成完成")

        run.report_text = report_text
        session.commit()

        dingtalk_sent = False
        if send_dingtalk:
            sender = DingTalkSender(settings)
            if not sender.enabled:
                _add_log(session, run_id, "INFO", "未配置钉钉 Webhook，跳过发送")
            else:
                try:
                    sender.send_weekly_report(
                        report_text,
                        week_start=fetch_result.week_start,
                        week_end=fetch_result.week_end,
                    )
                    dingtalk_sent = True
                    run.dingtalk_sent = 1
                    run.dingtalk_error = None
                    _add_log(session, run_id, "INFO", "钉钉发送成功")
                except Exception as exc:  # noqa: BLE001
                    run.dingtalk_sent = 0
                    run.dingtalk_error = str(exc)
                    _add_log(session, run_id, "ERROR", f"钉钉发送失败: {exc}")
                    # 周报已生成，钉钉失败仍记 success，但保留错误
        else:
            _add_log(session, run_id, "INFO", "已指定不发送钉钉")

        run.status = "success"
        run.finished_at = utcnow()
        session.commit()

        return PipelineResult(
            run_id=run_id,
            status="success",
            report_text=report_text,
            week_start=fetch_result.week_start,
            week_end=fetch_result.week_end,
            total_commits=fetch_result.total_commits,
            dingtalk_sent=dingtalk_sent,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("run %s 失败", run_id)
        try:
            session.rollback()
            run = session.get(Run, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = str(exc)
                run.finished_at = utcnow()
                session.add(
                    RunLog(
                        run_id=run_id,
                        level="ERROR",
                        message=f"任务失败: {exc}",
                        created_at=utcnow(),
                    )
                )
                session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("写入失败状态时出错")
        return PipelineResult(
            run_id=run_id,
            status="failed",
            error_message=str(exc),
        )
    finally:
        session.close()


def run_pipeline(options: RunOptions) -> PipelineResult:
    """创建 run 记录并同步执行（供 CLI）。"""
    init_db()
    factory = get_session_factory()
    with factory() as session:
        run = Run(
            trigger=options.trigger,
            status="pending",
            options_json=json.dumps(options.to_dict(), ensure_ascii=False),
        )
        session.add(run)
        session.commit()
        run_id = run.id

    from work_report.services.run_service import try_acquire_and_run_sync

    try:
        try_acquire_and_run_sync(run_id)
    except RuntimeError as exc:
        factory = get_session_factory()
        with factory() as session:
            run = session.get(Run, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = str(exc)
                run.finished_at = utcnow()
                session.commit()
        return PipelineResult(run_id=run_id, status="failed", error_message=str(exc))

    factory = get_session_factory()
    with factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            return PipelineResult(run_id=run_id, status="failed", error_message="记录丢失")
        return PipelineResult(
            run_id=run.id,
            status=run.status,
            report_text=run.report_text or "",
            week_start=run.week_start or "",
            week_end=run.week_end or "",
            total_commits=run.total_commits or 0,
            error_message=run.error_message,
            dingtalk_sent=bool(run.dingtalk_sent),
        )
