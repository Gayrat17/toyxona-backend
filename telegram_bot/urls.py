from django.urls import path
from .views import TelegramWebhookView, TelegramBotConfigView

urlpatterns = [
    path('webhook/', TelegramWebhookView.as_view(), name='telegram_webhook'),
    path('admin/bot-config/', TelegramBotConfigView.as_view(), name='admin_telegram_bot_config'),
]
