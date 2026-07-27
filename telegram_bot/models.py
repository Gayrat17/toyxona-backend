from django.db import models

class TelegramBotConfig(models.Model):
    """
    Singleton model to store Telegram Bot configuration dynamically.
    Ensures that only one record exists in the database.
    """
    bot_token = models.CharField(max_length=255, blank=True, null=True)
    bot_username = models.CharField(max_length=100, blank=True, null=True)
    bot_name = models.CharField(max_length=100, default="Restoran Admin Bot")
    short_description = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Telegram Bot Config"
        verbose_name_plural = "Telegram Bot Config"

    def save(self, *args, **kwargs):
        # Force ID to be 1 to preserve singleton pattern
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Telegram Bot: @{self.bot_username or 'Not configured'}"
