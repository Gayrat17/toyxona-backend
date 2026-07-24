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

def find_user_by_phone(phone_number):
    """
    Tries to find a User based on phone number candidates.
    Supports formats: +998XXXXXXXXX, 998XXXXXXXXX, XXXXXXXXX (9 digits).
    """
    if not phone_number:
        return None

    # Keep only digits
    digits = "".join(c for c in phone_number if c.isdigit())
    if not digits:
        return None

    candidates = [
        f"+{digits}",
        digits
    ]
    if len(digits) == 9:
        candidates.append(f"+998{digits}")
        candidates.append(f"998{digits}")

    return User.objects.filter(phone_number__in=candidates).first()


class TelegramWebhookView(APIView):
    """
    Webhook handler for incoming Telegram Bot API updates.
    Handles /start command, contact sharing, and callback queries.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        print(f"[BOT DEBUG] Telegram webhook received update: {data}")
        logger.info(f"Received telegram update: {data}")

        if "message" in data:
            self.handle_message(data["message"])
        elif "callback_query" in data:
            self.handle_callback_query(data["callback_query"])

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    def handle_message(self, message):
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        contact = message.get("contact")

        if not chat_id:
            return

        if text and text.strip().startswith("/start"):
            response_text = (
                "Assalomu alaykum! Tizimdagi hisobingizni ulanish uchun telefon raqamingizni yuboring."
            )
            reply_markup = {
                "keyboard": [
                    [
                        {
                            "text": "📱 Telefon raqamni yuborish",
                            "request_contact": True
                        }
                    ]
                ],
                "one_time_keyboard": True,
                "resize_keyboard": True
            }
            send_telegram_message(chat_id, response_text, reply_markup=reply_markup)

        elif contact:
            phone_number = contact.get("phone_number")
            user = find_user_by_phone(phone_number)

            if user:
                user.telegram_chat_id = chat_id
                user.save()
                response_text = (
                    "✅ Hisobingiz muvaffaqiyatli ulandi! Endi bron xabarlarini shu yerda qabul qilasiz."
                )
                reply_markup = {
                    "remove_keyboard": True
                }
                send_telegram_message(chat_id, response_text, reply_markup=reply_markup)
            else:
                response_text = (
                    f"Kechirasiz, tizimda {phone_number} raqamli foydalanuvchi topilmadi. "
                    "Iltimos, saytdagi raqamingiz orqali botga qayta murojaat qiling."
                )
                send_telegram_message(chat_id, response_text)

    def handle_callback_query(self, callback_query):
        query_id = callback_query.get("id")
        data = callback_query.get("data", "")
        from_user = callback_query.get("from", {})
        from_chat_id = from_user.get("id")
        message = callback_query.get("message", {})
        message_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")
        original_text = message.get("text", "")

        if not query_id:
            return

        match = re.match(r"^(confirm|reject)_booking_(hall|bar)_(\d+)$", data)
        if not match:
            answer_callback_query(query_id, text="Noma'lum so'rov formati.", show_alert=True)
            return

        action, booking_type, booking_id = match.groups()
        booking_id = int(booking_id)

        try:
            if booking_type == 'hall':
                booking = HallBooking.objects.select_related('hall', 'hall__owner').get(id=booking_id)
                owner = booking.hall.owner
            elif booking_type == 'bar':
                booking = BarBooking.objects.select_related('bar', 'bar__owner').get(id=booking_id)
                owner = booking.bar.owner
            else:
                answer_callback_query(query_id, text="Noma'lum bron turi.", show_alert=True)
                return

            clicking_user = User.objects.filter(telegram_chat_id=from_chat_id).first()
            is_owner = (owner.telegram_chat_id == from_chat_id)
            is_admin = (clicking_user is not None and clicking_user.role == 'ADMIN')

            if not (is_owner or is_admin):
                answer_callback_query(query_id, text="Kechirasiz, sizda ushbu amalni bajarish uchun ruxsat yo'q!", show_alert=True)
                return

            new_status = 'CONFIRMED' if action == 'confirm' else 'REJECTED'
            status_text = "TASDIQLANDI" if action == 'confirm' else "RAD ETILDI"
            status_emoji = "✅" if action == 'confirm' else "❌"

            booking.status = new_status
            booking.save()

            lines = original_text.split('\n')
            filtered_lines = []
            for line in lines:
                if "Mijoz bilan bog'lanib" in line or "Yangi Bron So'rovi" in line:
                    continue
                filtered_lines.append(line)

            status_line = f"\n\n<b>Holati: {status_emoji} Bron {status_text}! (Admin tomonidan)</b>"
            updated_text = f"{status_emoji} <b>Bron So'rovi Natijasi</b>\n\n" + "\n".join(filtered_lines).strip() + status_line

            edit_telegram_message(chat_id, message_id, updated_text, reply_markup={"inline_keyboard": []})
            answer_callback_query(query_id, text=f"Bron muvaffaqiyatli {status_text.lower()}!")

        except (HallBooking.DoesNotExist, BarBooking.DoesNotExist):
            answer_callback_query(query_id, text="Kechirasiz, ushbu bron bazadan topilmadi.", show_alert=True)
        except Exception as e:
            logger.exception(f"Error handling callback query: {e}")
            answer_callback_query(query_id, text="Tizimda xatolik yuz berdi.", show_alert=True)


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
