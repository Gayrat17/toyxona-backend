from django.db import IntegrityError, models


class TelegramBotConfig(models.Model):
    """Singleton configuration for the platform Telegram bot."""

    bot_token = models.CharField(max_length=255, blank=True, null=True)
    bot_username = models.CharField(max_length=100, blank=True, null=True)
    bot_name = models.CharField(max_length=100, default="To'yxona Admin Bot")
    short_description = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Telegram Bot Config"
        verbose_name_plural = "Telegram Bot Config"

    def save(self, *args, **kwargs):
        # There is one bot configuration for the whole platform.  Keeping a
        # stable primary key also makes ``load`` cheap and predictable.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        try:
            return cls.objects.get(pk=1)
        except cls.DoesNotExist:
            try:
                return cls.objects.create(pk=1)
            except IntegrityError:
                # Another worker may have initialized the singleton at the
                # same time; return its row instead of failing the request.
                return cls.objects.get(pk=1)

    def __str__(self) -> str:
        return f"Telegram Bot: @{self.bot_username or 'Not configured'}"
