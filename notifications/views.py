import logging
import re
import secrets
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import BarBooking, BaseBooking, HallBooking
from bookings.services import update_booking_status
from users.models import User as CustomUser, normalize_phone_number

logger = logging.getLogger(__name__)
User = get_user_model()



def find_user_by_phone(phone_number: str):
    """Find a user using the same canonicalization used at registration time."""

    if not phone_number:
        return None
    try:
        normalized = normalize_phone_number(phone_number)
        user = User.objects.filter(phone_number=normalized).first()
        if user:
            return user
    except ValueError:
        return None

    # Backwards compatibility for databases containing pre-normalization
    # values.  New accounts are always stored in canonical form.
    digits = "".join(character for character in str(phone_number) if character.isdigit())
    candidates = {f"+{digits}", digits}
    if len(digits) == 9:
        candidates.update({f"+998{digits}", f"998{digits}"})
    return User.objects.filter(phone_number__in=candidates).first()



def _parse_callback_query_data(data: str) -> Optional[Tuple[str, str, int]]:
    """Parse callback data as ``(action, venue_type, booking_id)``."""

    if not isinstance(data, str):
        return None
    match = re.fullmatch(r"(confirm|reject)_booking_(hall|bar)_(\d+)", data)
    if match:
        return match.group(1), match.group(2), int(match.group(3))

    legacy_match = re.fullmatch(r"(confirm|reject)_(hall|bar)_(\d+)", data)
    if legacy_match:
        return legacy_match.group(1), legacy_match.group(2), int(legacy_match.group(3))

    old_match = re.fullmatch(r"(confirm|reject)_booking_(\d+)", data)
    if old_match:
        return old_match.group(1), "hall", int(old_match.group(2))
    return None



def _fetch_booking_and_owner(
    booking_type: str, booking_id: int
) -> Tuple[Optional[Any], Optional[Any], str]:
    """Fetch only the model type encoded in callback data."""

    if booking_type == "hall":
        booking = HallBooking.objects.select_related("hall__owner").filter(pk=booking_id).first()
        return (booking, booking.hall.owner, "hall") if booking else (None, None, "hall")
    if booking_type == "bar":
        booking = BarBooking.objects.select_related("bar__owner").filter(pk=booking_id).first()
        return (booking, booking.bar.owner, "bar") if booking else (None, None, "bar")
    return None, None, booking_type



def _has_permission_to_manage_booking(from_chat_id: int, owner: Any) -> bool:
    """Allow the venue owner or a platform admin to use the Telegram button."""

    if from_chat_id is None:
        return False
    if owner and owner.telegram_chat_id is not None and owner.telegram_chat_id == from_chat_id:
        return True
    clicking_user = User.objects.filter(telegram_chat_id=from_chat_id).first()
    return bool(
        clicking_user
        and (getattr(clicking_user, "role", None) == CustomUser.Role.ADMIN or clicking_user.is_superuser)
    )


class TelegramWebhookSerializer(serializers.Serializer):
    """Loose schema for Telegram's update payload (validated by Telegram itself)."""

    update_id = serializers.IntegerField(required=False)
    message = serializers.JSONField(required=False)
    callback_query = serializers.JSONField(required=False)


class TelegramWebhookView(APIView):
    """Handle Telegram commands, contact sharing, and booking callbacks."""

    permission_classes = [AllowAny]
    serializer_class = TelegramWebhookSerializer

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        expected_secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        received_secret = request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
        if expected_secret and not secrets.compare_digest(received_secret, expected_secret):
            logger.warning("Rejected Telegram webhook request with an invalid secret")
            return Response({"status": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        try:
            data = request.data
            if not isinstance(data, dict):
                return Response({"status": "ok"}, status=status.HTTP_200_OK)
            if "message" in data:
                self.handle_message(data["message"])
            elif "callback_query" in data:
                self.handle_callback_query(data["callback_query"])
        except Exception:
            # Telegram retries non-2xx responses.  We log the failure but keep
            # the webhook acknowledgement stable for malformed/old updates.
            logger.exception("Error processing Telegram webhook update")
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    def handle_message(self, message: Dict[str, Any]) -> None:
        if not isinstance(message, dict):
            return
        chat_id = message.get("chat", {}).get("id")
        if chat_id is None:
            return
        text = str(message.get("text", "") or "").strip()
        contact = message.get("contact")

        try:
            import telegram_bot.views as bot_views

            command = text.split(maxsplit=1)[0].split("@", 1)[0] if text else ""
            if command == "/start":
                bot_views.send_telegram_message(
                    chat_id,
                    "Assalomu alaykum! Tizimdagi hisobingizni ulash uchun pastdagi tugma orqali telefon raqamingizni yuboring.",
                    reply_markup={
                        "keyboard": [[{"text": "📱 Telefon raqamni yuborish", "request_contact": True}]],
                        "one_time_keyboard": True,
                        "resize_keyboard": True,
                    },
                )
                return

            if not contact:
                return

            sender_id = message.get("from", {}).get("id")
            contact_user_id = contact.get("user_id")
            # Telegram normally includes user_id for a shared own contact.
            # Reject an explicitly different id so one user cannot bind another
            # person's account to their chat.
            if contact_user_id is not None and sender_id is not None and contact_user_id != sender_id:
                bot_views.send_telegram_message(
                    chat_id,
                    "Iltimos, faqat o'zingizning telefon raqamingizni yuboring.",
                )
                return

            phone_number = contact.get("phone_number")
            user = find_user_by_phone(phone_number)
            if user:
                user.telegram_chat_id = chat_id
                user.save(update_fields=["telegram_chat_id"])
                bot_views.send_telegram_message(
                    chat_id,
                    "✅ Hisobingiz muvaffaqiyatli ulandi! Endi bron xabarlarini shu yerda qabul qilasiz.",
                    reply_markup={"remove_keyboard": True},
                )
            else:
                bot_views.send_telegram_message(
                    chat_id,
                    f"Kechirasiz, tizimda {phone_number} raqamli foydalanuvchi topilmadi. Iltimos, saytda ro'yxatdan o'tgan raqamingiz orqali qayta urinib ko'ring.",
                )
        except Exception:
            logger.exception("Error handling Telegram message")

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        if not isinstance(callback_query, dict):
            return
        query_id = callback_query.get("id")
        if not query_id:
            return

        try:
            import telegram_bot.views as bot_views

            parsed = _parse_callback_query_data(callback_query.get("data", ""))
            if not parsed:
                bot_views.answer_callback_query(
                    query_id, text="Noma'lum so'rov formati.", show_alert=True
                )
                return

            action, booking_type, booking_id = parsed
            booking, owner, _ = _fetch_booking_and_owner(booking_type, booking_id)
            if not booking or not owner:
                bot_views.answer_callback_query(
                    query_id,
                    text="Kechirasiz, ushbu bron bazadan topilmadi.",
                    show_alert=True,
                )
                return

            from_chat_id = callback_query.get("from", {}).get("id")
            if not _has_permission_to_manage_booking(from_chat_id, owner):
                logger.warning("Unauthorized Telegram booking callback from chat_id=%s", from_chat_id)
                bot_views.answer_callback_query(
                    query_id,
                    text="Kechirasiz, sizda ushbu bronni boshqarish uchun ruxsat yo'q!",
                    show_alert=True,
                )
                return

            new_status = (
                BaseBooking.Status.CONFIRMED
                if action == "confirm"
                else BaseBooking.Status.REJECTED
            )
            try:
                update_booking_status(booking, new_status)
            except ValidationError as exc:
                detail = exc.detail
                message = str(detail)[:180]
                bot_views.answer_callback_query(query_id, text=message, show_alert=True)
                return

            status_text = "Tasdiqlandi" if action == "confirm" else "Rad etildi"
            status_emoji = "✅" if action == "confirm" else "❌"
            message = callback_query.get("message", {}) or {}
            message_id = message.get("message_id")
            chat_id = message.get("chat", {}).get("id")
            original_text = str(message.get("text", "") or "")
            lines = [
                line
                for line in original_text.split("\n")
                if "bog'lanib" not in line.lower() and "kutilmoqda" not in line.lower()
            ]
            updated_text = (
                f"{status_emoji} <b>Bron So'rovi Natijasi</b>\n\n"
                + "\n".join(lines).strip()
                + f"\n\n<b>Holati: {status_emoji} {status_text}!</b>"
            )
            if chat_id is not None and message_id is not None:
                bot_views.edit_telegram_message(
                    chat_id, message_id, updated_text, reply_markup={"inline_keyboard": []}
                )
            bot_views.answer_callback_query(
                query_id, text=f"Bron muvaffaqiyatli {status_text.lower()}! {status_emoji}"
            )
        except Exception:
            logger.exception("Exception handling Telegram callback query")
            try:
                import telegram_bot.views as bot_views

                bot_views.answer_callback_query(
                    query_id,
                    text="Tizimda xatolik yuz berdi. Iltimos qayta urining.",
                    show_alert=True,
                )
            except Exception:
                logger.exception("Could not acknowledge Telegram callback query")
