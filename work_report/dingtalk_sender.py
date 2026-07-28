"""钉钉自定义机器人群消息发送（Webhook）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any

import requests

from work_report.config import Settings

logger = logging.getLogger(__name__)


class DingTalkSender:
    """通过群机器人 Webhook 发送文本消息。"""

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.dingtalk_webhook)

    def _build_url(self) -> str:
        webhook = self.settings.dingtalk_webhook
        secret = self.settings.dingtalk_secret
        if not secret:
            return webhook

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        sep = "&" if "?" in webhook else "?"
        return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"

    def send_text(self, content: str, *, title: str | None = None) -> dict[str, Any]:
        """
        发送纯文本消息。

        title 非空时会作为首行前缀，便于在群里扫一眼识别。
        """
        if not self.enabled:
            raise RuntimeError("未配置 DINGTALK_WEBHOOK，无法发送钉钉消息")

        body = content.strip()
        if title:
            body = f"{title}\n\n{body}"

        if not body:
            raise ValueError("消息内容为空")

        payload = {
            "msgtype": "text",
            "text": {"content": body},
        }
        url = self._build_url()
        logger.info("发送钉钉群机器人消息，长度=%s", len(body))

        resp = self.session.post(
            url,
            json=payload,
            timeout=self.settings.dingtalk_timeout,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        resp.raise_for_status()
        data = resp.json()
        # 钉钉成功：{"errcode":0,"errmsg":"ok"}
        errcode = data.get("errcode", -1)
        if errcode != 0:
            raise RuntimeError(f"钉钉返回错误: errcode={errcode}, errmsg={data.get('errmsg')}")
        logger.info("钉钉消息发送成功")
        return data

    def send_weekly_report(
        self,
        report_text: str,
        *,
        week_start: str | None = None,
        week_end: str | None = None,
    ) -> dict[str, Any]:
        """
        发送周报正文。

        若 report_text 已含【周报】起止日期标题，则不再额外加 title 前缀，避免重复。
        """
        body = (report_text or "").strip()
        if body.startswith("【周报】"):
            return self.send_text(body, title=None)

        from work_report.llm_summarizer import format_report_header

        title = format_report_header(
            week_start or time.strftime("%Y-%m-%d"),
            week_end or week_start or time.strftime("%Y-%m-%d"),
        )
        return self.send_text(body, title=title)
