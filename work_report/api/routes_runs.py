"""运行任务 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from work_report.api.deps import DbSession
from work_report.services import run_service

router = APIRouter(tags=["runs"])


class CreateRunBody(BaseModel):
    skip_llm: bool = False
    send_dingtalk: bool = True
    if_last_workday: bool = False


@router.get("/runs")
def list_runs(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
) -> dict:
    return run_service.list_runs(db, page=page, size=size, status=status)


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: DbSession) -> dict:
    detail = run_service.get_run_detail(db, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return detail


@router.post("/runs", status_code=202)
def create_run(body: CreateRunBody, db: DbSession) -> dict:
    if run_service.is_busy():
        raise HTTPException(
            status_code=409,
            detail=f"已有任务正在运行 (id={run_service.get_running_id()})",
        )
    options = {
        "skip_llm": body.skip_llm,
        "send_dingtalk": body.send_dingtalk,
        "if_last_workday": body.if_last_workday,
        "trigger": "web",
    }
    run = run_service.create_run_record(db, trigger="web", options=options)
    db.commit()
    run_id = run.id
    run_service.start_run_background(run_id)
    return {"id": run_id, "status": "pending", "message": "任务已提交"}
