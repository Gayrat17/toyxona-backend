import logging

from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from telegram_bot.models import TelegramBotConfig
from telegram_bot.permissions import IsPlatformAdmin
from telegram_bot.services import (
    answer_callback_query,
    configure_telegram_bot,
    edit_telegram_message,
    send_telegram_message,
)
from notifications.views import TelegramWebhookView, find_user_by_phone

logger = logging.getLogger(__name__)
User = get_user_model()


class TelegramBotConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramBotConfig
        fields = (
            "bot_token",
            "bot_username",
            "bot_name",
            "short_description",
            "description",
            "webhook_url",
            "is_active",
            "updated_at",
        )
        read_only_fields = ("bot_username", "is_active", "updated_at")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        token = representation.get("bot_token")
        if token:
            representation["bot_token"] = (
                f"{token[:6]}...{token[-4:]}" if len(token) > 10 else "****"
            )
        return representation


class TelegramBotConfigView(APIView):
    """Read and update the platform Telegram bot configuration."""

    serializer_class = TelegramBotConfigSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        config_instance = TelegramBotConfig.load()
        serializer = TelegramBotConfigSerializer(config_instance, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        config_instance = TelegramBotConfig.load()
        serializer = TelegramBotConfigSerializer(
            config_instance,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        token_input = serializer.validated_data.get("bot_token")
        if token_input and ("..." in token_input or "*" in token_input):
            # The UI sends the masked value returned by GET when only metadata
            # was edited.  Never persist that mask as the real bot token.
            serializer.validated_data["bot_token"] = config_instance.bot_token

        instance = serializer.save()
        try:
            configure_telegram_bot(instance)
        except (ValueError, OSError) as exc:
            logger.warning("Telegram bot configuration failed: %s", exc)
            instance.refresh_from_db()
            return Response(
                {
                    "message": f"Telegram Bot sozlanishida xatolik: {exc}",
                    "config": TelegramBotConfigSerializer(instance).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Unexpected Telegram bot configuration failure")
            instance.refresh_from_db()
            return Response(
                {
                    "message": "Telegram Bot sozlanishida kutilmagan xatolik yuz berdi.",
                    "config": TelegramBotConfigSerializer(instance).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.refresh_from_db()
        return Response(
            {
                "message": "Telegram Bot muvaffaqiyatli sozlandi.",
                "config": TelegramBotConfigSerializer(instance).data,
            },
            status=status.HTTP_200_OK,
        )
