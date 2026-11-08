"""Best-effort notifications for finished update runs.

Notifications are opt-in and must never break an update: every transport error
is swallowed (and, when a reporter is available, surfaced as a warning).  The
webhook body deliberately carries only run metadata, never source URLs.
"""

import json
import urllib.parse
import urllib.request

from utils.config import config
from utils.i18n import t

_TIMEOUT_SECONDS = 8
_STATUS_LABELS = {
    "success": ("成功", "succeeded"),
    "completed": ("成功", "succeeded"),
    "completed_empty": ("完成（无结果）", "finished with no results"),
    "failed": ("失败", "failed"),
    "cancelled": ("已取消", "cancelled"),
}


def _language():
    return "zh" if str(getattr(config, "language", "zh_CN")).startswith("zh") else "en"


def _status_label(status):
    zh, en = _STATUS_LABELS.get(status, (status or "未知", status or "unknown"))
    return zh if _language() == "zh" else en


def build_message(status, details=None):
    details = details or {}
    if _language() == "zh":
        lines = [f"IPTV-API 运行{_status_label(status)}"]
        if details.get("message"):
            lines.append(f"说明：{details['message']}")
        if details.get("reason"):
            lines.append(f"原因：{details['reason']}")
        return "\n".join(lines)
    lines = [f"IPTV-API run {_status_label(status)}"]
    if details.get("message"):
        lines.append(f"Detail: {details['message']}")
    if details.get("reason"):
        lines.append(f"Reason: {details['reason']}")
    return "\n".join(lines)


def _should_send(status):
    success = status in {"success", "completed"}
    if success:
        return bool(config.notify_on_success)
    if status == "completed_empty":
        return bool(config.notify_on_success)
    return bool(config.notify_on_failure)


def _post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        return response.status


def _post_form(url, payload):
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        return response.status


def _send_webhook(message, status, details):
    url = (config.notify_webhook or "").strip()
    if not url:
        return False
    if not url.lower().startswith(("http://", "https://")):
        return False
    _post_json(url, {
        "text": message,
        "status": status,
        "run_id": details.get("run_id"),
        "reason": details.get("reason"),
        "message": details.get("message"),
    })
    return True


def _send_telegram(message):
    token = (config.notify_telegram_bot_token or "").strip()
    chat_id = (config.notify_telegram_chat_id or "").strip()
    if not token or not chat_id:
        return False
    _post_form(
        f"https://api.telegram.org/bot{token}/sendMessage",
        {"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"},
    )
    return True


def notify_run_finished(status, details=None, reporter=None):
    """Deliver the run result through every configured channel.

    Returns True when at least one transport accepted the message.  Never
    raises: a notification failure is not a run failure.
    """
    try:
        if not _should_send(status):
            return False
        message = build_message(status, details)
        delivered = False
        for name, sender in (
            ("webhook", lambda: _send_webhook(message, status, details or {})),
            ("telegram", lambda: _send_telegram(message)),
        ):
            try:
                delivered = sender() or delivered
            except Exception as exc:
                if reporter is not None:
                    reporter.warning(
                        "notify.failed",
                        f"{t('name.error')}: {name}: {exc}",
                        phase="complete",
                        transport=name,
                        error_type=type(exc).__name__,
                    )
        return delivered
    except Exception:
        return False
