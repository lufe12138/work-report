"""配置 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from work_report.api.deps import DbSession
from work_report.dingtalk_sender import DingTalkSender
from work_report.llm_summarizer import LLMSummarizer, PING_PROMPT
from work_report.services import settings_service

router = APIRouter(tags=["config"])


class ConfigUpdate(BaseModel):
    gitlab_url: str | None = None
    gitlab_token: str | None = None
    author_email: str | None = None
    project_ids: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_timeout: str | int | None = None
    llm_system_prompt: str | None = Field(default=None, max_length=50_000)
    timezone_offset_hours: str | int | None = None
    dingtalk_webhook: str | None = None
    dingtalk_secret: str | None = None
    dingtalk_timeout: str | int | None = None
    schedule_time: str | None = None
    schedule_days: str | None = None

    @field_validator("llm_system_prompt")
    @classmethod
    def validate_llm_system_prompt(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("周报提示词不能为空")
        return value


@router.get("/config")
def get_config(db: DbSession) -> dict[str, Any]:
    return settings_service.get_public_config(db)


@router.put("/config")
def put_config(body: ConfigUpdate, db: DbSession) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    # 统一转字符串
    normalized: dict[str, Any] = {}
    for k, v in payload.items():
        if v is None:
            continue
        normalized[k] = str(v).strip() if not isinstance(v, str) else v
    return settings_service.update_settings(db, normalized)


@router.post("/config/test-dingtalk")
def test_dingtalk(db: DbSession) -> dict[str, Any]:
    try:
        settings = settings_service.build_settings(db, require_llm=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sender = DingTalkSender(settings)
    if not sender.enabled:
        raise HTTPException(status_code=400, detail="未配置 dingtalk_webhook")
    try:
        sender.send_text(
            "work-report 钉钉机器人连通性测试成功。",
            title="【周报】测试消息",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"钉钉发送失败: {exc}") from exc
    return {"ok": True, "message": "钉钉测试消息已发送"}


@router.post("/config/test-llm")
def test_llm(db: DbSession) -> dict[str, Any]:
    try:
        settings = settings_service.build_settings(db, require_llm=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not (settings.llm_api_key or "").strip():
        raise HTTPException(status_code=400, detail="未配置 llm_api_key")
    try:
        reply = LLMSummarizer(settings).ping()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}") from exc
    return {
        "ok": True,
        "message": "LLM 测活成功",
        "prompt": PING_PROMPT,
        "reply": reply,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
    }
