"""Small, defensive wrappers around the Telegram Bot HTTP API."""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_telegram_bot_token() -> str:
    """Return the database token, falling back to the environment setting."""

    from telegram_bot.models import TelegramBotConfig

    try:
        token = TelegramBotConfig.objects.values_list("bot_token", flat=True).first()
        if token:
            return token.strip()
    except Exception:
        # A notification must not make an otherwise healthy API request fail if
        # the optional configuration table is temporarily unavailable.
        logger.exception("Could not load Telegram bot configuration")
    return str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _response_data(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _timeout() -> int:
    return int(getattr(settings, "TELEGRAM_API_TIMEOUT", 10))


def _post(token: str, method: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    try:
        response = requests.post(_api_url(token, method), json=payload or {}, timeout=_timeout())
        data = _response_data(response)
        if not response.ok or not data.get("ok"):
            logger.error(
                "Telegram API %s failed: http_status=%s description=%s",
                method,
                response.status_code,
                data.get("description", "unknown error"),
            )
        return data or {"ok": False, "description": "Telegram returned an invalid response"}
    except requests.RequestException as exc:
        logger.exception("Telegram API %s request failed: %s", method, exc)
        return {"ok": False, "description": str(exc)}


def configure_telegram_bot(config_instance) -> bool:
    """Validate and configure a bot, marking the singleton active on success."""

    token = (config_instance.bot_token or "").strip()
    if not token:
        config_instance.is_active = False
        config_instance.save(update_fields=["is_active", "updated_at"])
        raise ValueError("Bot tokeni bo'sh bo'lishi mumkin emas.")

    me = _request_get(token, "getMe")
    if not me.get("ok"):
        config_instance.is_active = False
        config_instance.save(update_fields=["is_active", "updated_at"])
        raise ValueError(f"getMe xatosi: {me.get('description', 'Unauthorized')}")

    config_instance.bot_token = token
    config_instance.bot_username = me.get("result", {}).get("username")

    # These are best-effort metadata calls.  A failed description should not
    # make a valid token unusable; getMe and setWebhook remain mandatory.
    if config_instance.bot_name:
        _post(token, "setMyName", {"name": config_instance.bot_name})
    if config_instance.description:
        _post(token, "setMyDescription", {"description": config_instance.description})
    if config_instance.short_description:
        _post(
            token,
            "setMyShortDescription",
            {"short_description": config_instance.short_description},
        )
    _post(
        token,
        "setMyCommands",
        {"commands": [{"command": "start", "description": "Hisobni ulash va bronlarni qabul qilish"}]},
    )

    webhook_url = (config_instance.webhook_url or "").strip()
    if webhook_url:
        webhook = set_telegram_webhook(webhook_url, token=token)
        if not webhook.get("ok"):
            config_instance.is_active = False
            config_instance.save(update_fields=["is_active", "updated_at"])
            raise ValueError(f"Webhook xatosi: {webhook.get('description', 'unknown error')}")

    config_instance.is_active = True
    config_instance.save(update_fields=["bot_token", "bot_username", "is_active", "updated_at"])
    return True


def set_telegram_webhook(
    webhook_url: Optional[str] = None,
    *,
    token: Optional[str] = None,
    delete: bool = False,
) -> dict[str, Any]:
    """Set or remove the bot webhook and return Telegram's response."""

    token = (token or get_telegram_bot_token()).strip()
    if not token:
        return {"ok": False, "description": "Telegram bot token not configured"}
    if delete:
        return _post(token, "deleteWebhook")
    if not webhook_url:
        return {"ok": False, "description": "webhook_url is required"}

    webhook_url = webhook_url.strip()
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        return {"ok": False, "description": "Telegram webhook URL HTTPS bo'lishi kerak."}
    payload: dict[str, Any] = {"url": webhook_url}
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    if secret:
        payload["secret_token"] = secret
    return _post(token, "setWebhook", payload)


def _request_get(token: str, method: str) -> dict[str, Any]:
    try:
        response = requests.get(_api_url(token, method), timeout=_timeout())
        data = _response_data(response)
        return data or {"ok": False, "description": "Telegram returned an invalid response"}
    except requests.RequestException as exc:
        logger.exception("Telegram API %s request failed: %s", method, exc)
        return {"ok": False, "description": str(exc)}


def send_telegram_message(
    chat_id: int,
    text: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Send an HTML-formatted Telegram message."""

    token = get_telegram_bot_token()
    if not token:
        logger.warning("Telegram bot token is not configured")
        return {"ok": False, "description": "Telegram bot token not configured"}
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post(token, "sendMessage", payload)


def edit_telegram_message(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Edit an existing Telegram message."""

    token = get_telegram_bot_token()
    if not token:
        logger.warning("Telegram bot token is not configured")
        return {"ok": False, "description": "Telegram bot token not configured"}
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post(token, "editMessageText", payload)


def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> dict[str, Any]:
    """Stop the loading spinner after an inline-button click."""

    token = get_telegram_bot_token()
    if not token:
        logger.warning("Telegram bot token is not configured")
        return {"ok": False, "description": "Telegram bot token not configured"}
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload.update({"text": text, "show_alert": show_alert})
    return _post(token, "answerCallbackQuery", payload)
