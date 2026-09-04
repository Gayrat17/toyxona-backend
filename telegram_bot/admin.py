from django.contrib import admin

from .models import TelegramBotConfig


@admin.register(TelegramBotConfig)
class TelegramBotConfigAdmin(admin.ModelAdmin):
    list_display = ("bot_name", "bot_username", "is_active", "updated_at")
    readonly_fields = ("bot_username", "is_active", "updated_at")

    def has_add_permission(self, request):
        # The model is a singleton; the change form is enough.
        return not TelegramBotConfig.objects.exists()
