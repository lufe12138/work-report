"""运行记录查询与触发。"""

from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from work_report.db.models import Run, RunCommit, RunLog
from work_report.db.session import get_session_factory
from work_report.timeutil import format_datetime, format_maybe

# 进程内单任务锁
_run_lock = threading.Lock()
_running_id: int | None = None


def is_busy() -> bool:
    return _run_lock.locked() or _running_id is not None


def get_running_id() -> int | None:
    return _running_id


def run_to_summary(run: Run) -> dict[str, Any]:
    return {
        "id": run.id,
        "trigger": run.trigger,
        "status": run.status,
        "week_start": format_maybe(run.week_start) or run.week_start,
        "week_end": format_maybe(run.week_end) or run.week_end,
        "total_commits": run.total_commits,
        "project_count": run.project_count,
        "dingtalk_sent": bool(run.dingtalk_sent),
        "error_message": run.error_message,
        "holiday_reason": run.holiday_reason,
        "started_at": format_maybe(run.started_at),
        "finished_at": format_maybe(run.finished_at),
        "created_at": format_maybe(run.created_at),
    }


def run_to_detail(run: Run) -> dict[str, Any]:
    data = run_to_summary(run)
    try:
        options = json.loads(run.options_json or "{}")
    except json.JSONDecodeError:
        options = {}
    data.update(
        {
            "options": options,
            "report_text": run.report_text or "",
            "dingtalk_error": run.dingtalk_error,
            "commits": [
                {
                    "id": c.id,
                    "project_id": c.project_id,
                    "project_name": c.project_name,
                    "short_id": c.short_id,
                    "title": c.title,
                    "message": c.message,
                    "author_name": c.author_name,
                    "author_email": c.author_email,
                    "created_at": format_datetime(c.commit_created_at) or c.commit_created_at,
                }
                for c in run.commits
            ],
            "logs": [
                {
                    "id": log.id,
                    "level": log.level,
                    "message": log.message,
                    "created_at": format_maybe(log.created_at),
                }
                for log in run.logs
            ],
        }
    )
    return data


def list_runs(
    session: Session,
    *,
    page: int = 1,
    size: int = 20,
    status: str | None = None,
) -> dict[str, Any]:
    page = max(1, page)
    size = min(100, max(1, size))
    stmt = select(Run)
    count_stmt = select(func.count()).select_from(Run)
    if status:
        stmt = stmt.where(Run.status == status)
        count_stmt = count_stmt.where(Run.status == status)
    total = session.scalar(count_stmt) or 0
    rows = session.scalars(
        stmt.order_by(Run.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [run_to_summary(r) for r in rows],
    }


def get_run_detail(session: Session, run_id: int) -> dict[str, Any] | None:
    run = session.scalar(
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.commits), selectinload(Run.logs))
    )
    if run is None:
        return None
    return run_to_detail(run)


def dashboard(session: Session) -> dict[str, Any]:
    total = session.scalar(select(func.count()).select_from(Run)) or 0
    success = session.scalar(
        select(func.count()).select_from(Run).where(Run.status == "success")
    ) or 0
    failed = session.scalar(
        select(func.count()).select_from(Run).where(Run.status == "failed")
    ) or 0
    running = session.scalar(
        select(func.count()).select_from(Run).where(Run.status == "running")
    ) or 0
    recent = session.scalars(select(Run).order_by(Run.id.desc()).limit(5)).all()
    return {
        "total_runs": total,
        "success_runs": success,
        "failed_runs": failed,
        "running_runs": running,
        "busy": is_busy(),
        "running_id": get_running_id(),
        "recent": [run_to_summary(r) for r in recent],
    }


def create_run_record(
    session: Session,
    *,
    trigger: str,
    options: dict[str, Any],
) -> Run:
    run = Run(
        trigger=trigger,
        status="pending",
        options_json=json.dumps(options, ensure_ascii=False),
    )
    session.add(run)
    session.flush()
    return run


def start_run_background(run_id: int) -> None:
    """在后台线程执行 pipeline。"""
    global _running_id

    if not _run_lock.acquire(blocking=False):
        factory = get_session_factory()
        with factory() as session:
            run = session.get(Run, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = "已有任务正在运行，请稍后再试"
                session.commit()
        return

    _running_id = run_id

    def _worker() -> None:
        global _running_id
        try:
            from work_report.pipeline import execute_run

            execute_run(run_id)
        finally:
            _running_id = None
            _run_lock.release()

    thread = threading.Thread(target=_worker, name=f"run-{run_id}", daemon=True)
    thread.start()


def try_acquire_and_run_sync(run_id: int) -> None:
    """CLI 同步执行（也占锁）。"""
    global _running_id
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("已有任务正在运行")
    _running_id = run_id
    try:
        from work_report.pipeline import execute_run

        execute_run(run_id)
    finally:
        _running_id = None
        _run_lock.release()
