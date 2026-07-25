import logging
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status, serializers
from django.db.models import Q
from django.contrib.auth import get_user_model
from bookings.models import HallBooking, BarBooking
from telegram_bot.models import TelegramBotConfig
from telegram_bot.permissions import IsPlatformAdmin
from telegram_bot.services import send_telegram_message, edit_telegram_message, answer_callback_query, configure_telegram_bot

logger = logging.getLogger(__name__)
User = get_user_model()

from notifications.views import TelegramWebhookView, find_user_by_phone


class TelegramBotConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramBotConfig
        fields = (
            'bot_token',
            'bot_username',
            'bot_name',
            'short_description',
            'description',
            'webhook_url',
            'is_active',
            'updated_at'
        )
        read_only_fields = ('bot_username', 'is_active', 'updated_at')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        token = ret.get('bot_token')
        if token and len(token) > 10:
            ret['bot_token'] = f"{token[:6]}...{token[-4:]}"
        return ret


class TelegramBotConfigView(APIView):
    """
    Superadmin view to retrieve and configure Telegram Bot settings.
    """
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request, *args, **kwargs):
        config_inst = TelegramBotConfig.load()
        serializer = TelegramBotConfigSerializer(config_inst)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        config_inst = TelegramBotConfig.load()
        serializer = TelegramBotConfigSerializer(config_inst, data=request.data, partial=True)
        if serializer.is_valid():
            token_input = serializer.validated_data.get('bot_token')
            if token_input and ('...' in token_input or '*' in token_input):
                serializer.validated_data['bot_token'] = config_inst.bot_token

            instance = serializer.save()

            try:
                configure_telegram_bot(instance)
                instance.refresh_from_db()
                return Response({
                    "message": "Bot tokeni qabul qilindi, nomi o'zgartirildi va Webhook muvaffaqiyatli ulandi!",
                    "config": TelegramBotConfigSerializer(instance).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Failed to configure Telegram Bot: {e}")
                return Response({
                    "message": f"Telegram Bot sozlanishida xatolik: {str(e)}",
                    "config": TelegramBotConfigSerializer(instance).data
                }, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
