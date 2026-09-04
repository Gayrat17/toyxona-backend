from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from telegram_bot.models import TelegramBotConfig
from telegram_bot.services import get_telegram_bot_token, set_telegram_webhook


class Command(BaseCommand):
    help = "Set or delete the Telegram bot webhook URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            help="Full webhook URL or site base URL (https://example.com).",
        )
        parser.add_argument("--delete", action="store_true", help="Delete the current webhook.")

    def handle(self, *args, **options):
        delete = options["delete"]
        raw_url = (options.get("url") or "").strip()
        if delete and raw_url:
            raise CommandError("--url va --delete bir vaqtda ishlatilmaydi.")
        if not delete and not raw_url:
            raise CommandError("--url kiriting yoki --delete dan foydalaning.")

        token = get_telegram_bot_token()
        if not token:
            raise CommandError("Telegram bot tokeni database yoki settingsda sozlanmagan.")

        webhook_url = None
        if not delete:
            webhook_url = raw_url.rstrip("/")
            parsed = urlparse(webhook_url)
            if not (parsed.path.endswith("/webhook") or parsed.path.endswith("/webhook/")):
                webhook_url += "/api/v1/bot/webhook/"

        result = set_telegram_webhook(webhook_url, token=token, delete=delete)
        if not result.get("ok"):
            raise CommandError(result.get("description", "Telegram webhook xatosi"))

        config = TelegramBotConfig.load()
        if delete:
            config.webhook_url = None
        else:
            config.webhook_url = webhook_url
        config.save(update_fields=["webhook_url", "updated_at"])

        if delete:
            self.stdout.write(self.style.SUCCESS("Telegram webhook o'chirildi."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Telegram webhook o'rnatildi: {webhook_url}"))
