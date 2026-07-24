import requests
from django.core.management.base import BaseCommand
from telegram_bot.services import get_telegram_bot_token

class Command(BaseCommand):
    help = "Sets or deletes the Telegram bot webhook URL."

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='The base URL or full webhook URL (e.g., https://yourdomain.com or https://yourdomain.com/api/v1/bot/webhook/)',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete the current webhook',
        )

    def handle(self, *args, **options):
        token = get_telegram_bot_token()
        if not token:
            self.stderr.write(self.style.ERROR("Telegram Bot Token is not configured in database or settings."))
            return

        delete = options['delete']
        if delete:
            url = f"https://api.telegram.org/bot{token}/deleteWebhook"
            try:
                response = requests.post(url, timeout=10)
                response_data = response.json()
                if response_data.get("ok"):
                    self.stdout.write(self.style.SUCCESS("Successfully deleted Telegram webhook."))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to delete webhook: {response_data.get('description')}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error connecting to Telegram: {e}"))
            return

        raw_url = options['url']
        if not raw_url:
            self.stderr.write(self.style.ERROR("Please provide a URL via --url option or use --delete."))
            return

        webhook_url = raw_url.strip()
        if not (webhook_url.endswith('/webhook/') or webhook_url.endswith('/webhook')):
            if webhook_url.endswith('/'):
                webhook_url = webhook_url[:-1]
            webhook_url = f"{webhook_url}/api/v1/bot/webhook/"

        self.stdout.write(f"Setting webhook to: {webhook_url}")
        
        telegram_url = f"https://api.telegram.org/bot{token}/setWebhook"
        payload = {
            "url": webhook_url
        }

        try:
            response = requests.post(telegram_url, json=payload, timeout=10)
            response_data = response.json()
            if response_data.get("ok"):
                self.stdout.write(self.style.SUCCESS(f"Successfully set Telegram webhook to {webhook_url}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to set webhook: {response_data.get('description')}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error connecting to Telegram: {e}"))
