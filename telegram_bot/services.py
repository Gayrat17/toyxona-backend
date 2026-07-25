import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def get_telegram_bot_token() -> str:
    """
    Returns the configured bot token from database TelegramBotConfig singleton.
    Falls back to settings.TELEGRAM_BOT_TOKEN.
    """
    from telegram_bot.models import TelegramBotConfig
    try:
        config = TelegramBotConfig.objects.first()
        if config and config.bot_token:
            return config.bot_token
    except Exception as e:
        logger.error(f"Error loading TelegramBotConfig from database: {e}")
    return getattr(settings, 'TELEGRAM_BOT_TOKEN', '')


def configure_telegram_bot(config_instance) -> bool:
    """
    Auto-configures the Telegram Bot with name, description, commands, and webhook.
    Raises ValueError on Telegram API failure, sets config_instance.is_active = False.
    """
    token = config_instance.bot_token
    if not token:
        config_instance.is_active = False
        config_instance.save()
        raise ValueError("Bot token is empty.")

    base_url = f"https://api.telegram.org/bot{token}"
    
    # 1. getMe
    try:
        res = requests.get(f"{base_url}/getMe", timeout=10)
        res_data = res.json()
        if not res_data.get("ok"):
            error_desc = res_data.get("description", "Unauthorized")
            config_instance.is_active = False
            config_instance.save()
            raise ValueError(f"getMe failed: {error_desc}")
        
        bot_info = res_data["result"]
        config_instance.bot_username = bot_info.get("username")
    except Exception as e:
        config_instance.is_active = False
        config_instance.save()
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Failed to connect to Telegram getMe: {str(e)}")

    # 2. setMyName
    if config_instance.bot_name:
        try:
            res = requests.post(f"{base_url}/setMyName", json={"name": config_instance.bot_name}, timeout=10)
            if not res.json().get("ok"):
                logger.warning(f"setMyName failed: {res.json()}")
        except Exception as e:
            logger.warning(f"Failed calling setMyName: {e}")

    # 3. setMyDescription
    if config_instance.description:
        try:
            res = requests.post(f"{base_url}/setMyDescription", json={"description": config_instance.description}, timeout=10)
            if not res.json().get("ok"):
                logger.warning(f"setMyDescription failed: {res.json()}")
        except Exception as e:
            logger.warning(f"Failed calling setMyDescription: {e}")

    # 4. setMyShortDescription
    if config_instance.short_description:
        try:
            res = requests.post(f"{base_url}/setMyShortDescription", json={"short_description": config_instance.short_description}, timeout=10)
            if not res.json().get("ok"):
                logger.warning(f"setMyShortDescription failed: {res.json()}")
        except Exception as e:
            logger.warning(f"Failed calling setMyShortDescription: {e}")

    # 5. setMyCommands
    commands = [{"command": "start", "description": "Hisobni ulanish va bronlarni qabul qilish"}]
    try:
        res = requests.post(f"{base_url}/setMyCommands", json={"commands": commands}, timeout=10)
        if not res.json().get("ok"):
            logger.warning(f"setMyCommands failed: {res.json()}")
    except Exception as e:
        logger.warning(f"Failed calling setMyCommands: {e}")

    # 6. setWebhook
    if config_instance.webhook_url:
        try:
            webhook_res = requests.post(f"{base_url}/setWebhook", json={"url": config_instance.webhook_url}, timeout=10)
            webhook_data = webhook_res.json()
            if not webhook_data.get("ok"):
                error_desc = webhook_data.get("description", "Unknown webhook error")
                config_instance.is_active = False
                config_instance.save()
                raise ValueError(f"setWebhook failed: {error_desc}")
        except Exception as e:
            config_instance.is_active = False
            config_instance.save()
            if isinstance(e, ValueError):
                raise e
            raise ValueError(f"Failed calling setWebhook: {str(e)}")

    # Set active and save
    config_instance.is_active = True
    config_instance.save()
    return True


def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None) -> dict:
    """
    Sends a message to a Telegram chat using the configured bot token.
    Supports HTML parse mode and custom inline/reply keyboards.
    """
    token = get_telegram_bot_token()
    if not token:
        logger.error("Telegram bot token is not configured.")
        return {"ok": False, "description": "Telegram bot token not configured"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            logger.error(f"[BOT ERROR] Telegram API xatoligi: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        logger.exception(f"[BOT ERROR] Exception during send_telegram_message: {str(e)}")
        return {"ok": False, "description": str(e)}


def edit_telegram_message(chat_id: int, message_id: int, text: str, reply_markup: dict = None) -> dict:
    """
    Edits a previously sent message in a Telegram chat.
    Supports HTML parse mode and custom inline keyboards.
    """
    token = get_telegram_bot_token()
    if not token:
        logger.error("Telegram bot token is not configured.")
        return {"ok": False, "description": "Telegram bot token not configured"}

    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            logger.error(f"[BOT ERROR] Telegram API xatoligi: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        logger.exception(f"[BOT ERROR] Exception during edit_telegram_message: {str(e)}")
        return {"ok": False, "description": str(e)}


def answer_callback_query(callback_query_id: str, text: str = None, show_alert: bool = False) -> dict:
    """
    Answers a callback query from an inline keyboard.
    """
    token = get_telegram_bot_token()
    if not token:
        logger.error("Telegram bot token is not configured.")
        return {"ok": False, "description": "Telegram bot token not configured"}

    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
    }
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert

    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            logger.error(f"[BOT ERROR] Telegram API xatoligi: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        logger.exception(f"[BOT ERROR] Exception during answer_callback_query: {str(e)}")
        return {"ok": False, "description": str(e)}

