"""从 .env 与项目映射文件加载配置。"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（work-report/）
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT_NAMES_FILE = ROOT_DIR / "project_names.json"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """运行时配置。"""

    gitlab_url: str
    gitlab_token: str
    author_email: str
    project_ids: list[int]

    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout: int

    timezone_offset_hours: int

    # 钉钉群机器人（可选）
    dingtalk_webhook: str
    dingtalk_secret: str
    dingtalk_timeout: int

    # GitLab 项目名 -> 业务中文名（用户维护）
    project_name_map: dict[str, str] = field(default_factory=dict)

    def display_project_name(self, project_name: str) -> str:
        """
        返回周报用的项目展示名。

        有映射: 示例业务数据统计（example_backend）
        无映射: example_backend
        """
        zh = self.project_name_map.get(project_name, "").strip()
        if zh:
            return f"{zh}（{project_name}）"
        return project_name


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"缺少必要配置项: {name}，请在 .env 中设置")
    return value


def _parse_project_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ids.append(int(part))
    if not ids:
        raise ValueError("PROJECT_IDS 为空，请至少配置一个项目 ID")
    return ids


def load_project_name_map(path: str | Path | None = None) -> dict[str, str]:
    """
    加载项目中文名映射。

    文件格式（JSON 对象）::
        {
          "example_backend": "示例业务数据统计",
          "example_frontend": "示例前端应用"
        }
    """
    file_path = Path(path) if path else Path(
        os.getenv("PROJECT_NAMES_FILE", str(DEFAULT_PROJECT_NAMES_FILE))
    )
    if not file_path.is_file():
        logger.warning("项目中文名映射文件不存在: %s，将不使用固定中文名", file_path)
        return {}

    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"项目中文名映射文件 JSON 无效: {file_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise TypeError(f"项目中文名映射文件必须是 JSON 对象: {file_path}")

    result: dict[str, str] = {}
    for key, value in raw.items():
        k = str(key).strip()
        v = str(value).strip() if value is not None else ""
        if k and v:
            result[k] = v
    logger.info("已加载项目中文名映射 %s 条（%s）", len(result), file_path)
    return result


def load_settings(
    env_file: str | Path | None = None,
    *,
    require_llm: bool = True,
) -> Settings:
    """
    加载 .env 并返回 Settings。

    env_file 默认为项目根目录下的 .env。
    require_llm=False 时不强制要求 LLM_API_KEY（用于 --skip-llm）。
    """
    path = Path(env_file) if env_file else ROOT_DIR / ".env"
    load_dotenv(path, override=False)

    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    if require_llm and not llm_api_key:
        raise ValueError("缺少必要配置项: LLM_API_KEY，请在 .env 中设置")

    return Settings(
        gitlab_url=_require("GITLAB_URL").rstrip("/"),
        gitlab_token=_require("GITLAB_TOKEN"),
        author_email=_require("AUTHOR_EMAIL"),
        project_ids=_parse_project_ids(_require("PROJECT_IDS")),
        llm_api_key=llm_api_key,
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        timezone_offset_hours=int(os.getenv("TIMEZONE_OFFSET_HOURS", "8")),
        dingtalk_webhook=os.getenv("DINGTALK_WEBHOOK", "").strip(),
        dingtalk_secret=os.getenv("DINGTALK_SECRET", "").strip(),
        dingtalk_timeout=int(os.getenv("DINGTALK_TIMEOUT", "15")),
        project_name_map=load_project_name_map(),
    )
