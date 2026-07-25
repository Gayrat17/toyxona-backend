import logging
import re
from typing import Optional, Tuple, Any, Dict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.contrib.auth import get_user_model
from bookings.models import HallBooking, BarBooking, BaseBooking
from users.models import User as CustomUser
from telegram_bot.services import (
    send_telegram_message,
    edit_telegram_message,
    answer_callback_query
)

logger = logging.getLogger(__name__)
User = get_user_model()


def find_user_by_phone(phone_number: str) -> Optional[CustomUser]:
    """
    Finds user by phone number trying multiple common formats (+998..., 998..., 9 digits).
    """
    if not phone_number:
        return None

    digits = "".join(c for c in phone_number if c.isdigit())
    if not digits:
        return None

    candidates = [f"+{digits}", digits]
    if len(digits) == 9:
        candidates.extend([f"+998{digits}", f"998{digits}"])

    return User.objects.filter(phone_number__in=candidates).first()


def _parse_callback_query_data(data: str) -> Optional[Tuple[str, str, int]]:
    """
    Parses telegram callback query string.
    Returns (action, booking_type, booking_id) or None if format invalid.
    """
    match = (
        re.match(r"^(confirm|reject)_booking_(hall|bar)_(\d+)$", data) or
        re.match(r"^(confirm|reject)_(hall|bar)_(\d+)$", data) or
        re.match(r"^(confirm|reject)_booking_(\d+)$", data)
    )

    if not match:
        return None

    groups = match.groups()
    action = groups[0]  # 'confirm' or 'reject'

    if len(groups) == 3:
        booking_type = groups[1]  # 'hall' or 'bar'
        booking_id = int(groups[2])
    else:
        booking_type = 'hall'
        booking_id = int(groups[1])

    return action, booking_type, booking_id


def _fetch_booking_and_owner(booking_type: str, booking_id: int) -> Tuple[Optional[Any], Optional[Any], str]:
    """
    Retrieves booking instance and venue owner for hall or bar booking with fallback.
    Returns (booking_instance, owner_user, actual_booking_type).
    """
    if booking_type == 'hall':
        try:
            booking = HallBooking.objects.select_related('hall', 'hall__owner').get(id=booking_id)
            return booking, booking.hall.owner, 'hall'
        except HallBooking.DoesNotExist:
            booking = BarBooking.objects.select_related('bar', 'bar__owner').filter(id=booking_id).first()
            if booking:
                return booking, booking.bar.owner, 'bar'
    elif booking_type == 'bar':
        try:
            booking = BarBooking.objects.select_related('bar', 'bar__owner').get(id=booking_id)
            return booking, booking.bar.owner, 'bar'
        except BarBooking.DoesNotExist:
            booking = HallBooking.objects.select_related('hall', 'hall__owner').filter(id=booking_id).first()
            if booking:
                return booking, booking.hall.owner, 'hall'

    return None, None, booking_type


def _has_permission_to_manage_booking(from_chat_id: int, owner: Any) -> bool:
    """Checks whether the Telegram user clicking the button is venue owner or platform admin."""
    if owner and owner.telegram_chat_id == from_chat_id:
        return True

    clicking_user = User.objects.filter(telegram_chat_id=from_chat_id).first()
    if clicking_user and getattr(clicking_user, 'role', None) == CustomUser.Role.ADMIN:
        return True

    return False


class TelegramWebhookView(APIView):
    """
    DRF APIView for handling incoming Telegram Webhook updates.
    Handles /start command, phone number sharing (contact), and Callback Queries (Confirm/Reject buttons).
    Guarantees returning HTTP 200 OK to Telegram server to prevent update retries.
    """
    permission_classes = [AllowAny]

    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        try:
            data = request.data
            logger.info(f"Received Telegram webhook update: {data}")

            if "message" in data:
                self.handle_message(data["message"])
            elif "callback_query" in data:
                self.handle_callback_query(data["callback_query"])

        except Exception as e:
            # Log error details and still return 200 OK so Telegram server won't retry endless updates
            logger.error(f"Error processing Telegram webhook request: {e}", exc_info=True)

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    def handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handles incoming standard chat messages (/start and contact sharing).
        """
        try:
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            contact = message.get("contact")

            if not chat_id:
                return

            # 1. Handle /start command
            if text and text.strip().startswith("/start"):
                response_text = (
                    "Assalomu alaykum! Tizimdagi hisobingizni ulanish uchun "
                    "pastdagi tugma orqali telefon raqamingizni yuboring."
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
                import telegram_bot.views as bot_views
                bot_views.send_telegram_message(chat_id, response_text, reply_markup=reply_markup)

            # 2. Handle Contact sharing
            elif contact:
                phone_number = contact.get("phone_number")
                user = find_user_by_phone(phone_number)

                import telegram_bot.views as bot_views
                if user:
                    user.telegram_chat_id = chat_id
                    user.save()
                    response_text = (
                        "✅ Hisobingiz muvaffaqiyatli ulandi! "
                        "Endi bron xabarlarini shu yerda qabul qilasiz."
                    )
                    reply_markup = {"remove_keyboard": True}
                    bot_views.send_telegram_message(chat_id, response_text, reply_markup=reply_markup)
                else:
                    response_text = (
                        f"Kechirasiz, tizimda {phone_number} raqamli foydalanuvchi topilmadi. "
                        "Iltimos, saytda ro'yxatdan o'tgan raqamingiz orqali qayta urinib ko'ring."
                    )
                    bot_views.send_telegram_message(chat_id, response_text)

        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}", exc_info=True)

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """
        Handles Callback Queries (Inline button clicks: Tasdiqlash / Rad etish).
        """
        query_id = callback_query.get("id")
        data = callback_query.get("data", "")
        from_chat_id = callback_query.get("from", {}).get("id")
        message = callback_query.get("message", {})
        message_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")
        original_text = message.get("text", "")

        if not query_id:
            return

        try:
            import telegram_bot.views as bot_views
            parsed = _parse_callback_query_data(data)
            if not parsed:
                logger.warning(f"Unrecognized callback query data format: {data}")
                bot_views.answer_callback_query(query_id, text="Noma'lum so'rov formati.", show_alert=True)
                return

            action, booking_type, booking_id = parsed
            booking, owner, booking_type = _fetch_booking_and_owner(booking_type, booking_id)

            if not booking or not owner:
                logger.error(f"Booking ID {booking_id} ({booking_type}) not found in database.")
                bot_views.answer_callback_query(query_id, text="Kechirasiz, ushbu bron bazadan topilmadi.", show_alert=True)
                return

            if not _has_permission_to_manage_booking(from_chat_id, owner):
                logger.warning(f"Unauthorized callback query attempt from chat_id {from_chat_id}")
                bot_views.answer_callback_query(query_id, text="Kechirasiz, sizda ushbu bronni boshqarish uchun ruxsat yo'q!", show_alert=True)
                return

            # Update booking status
            new_status = BaseBooking.Status.CONFIRMED if action == 'confirm' else BaseBooking.Status.REJECTED
            status_text = "Tasdiqlandi" if action == 'confirm' else "Rad etildi"
            status_emoji = "✅" if action == 'confirm' else "❌"

            booking.status = new_status
            booking.save()
            logger.info(f"Booking {booking_id} ({booking_type}) status updated to {new_status} by chat_id {from_chat_id}")

            # Format updated telegram notification message
            lines = original_text.split('\n')
            filtered_lines = [
                line for line in lines
                if "bog'lanib" not in line.lower() and "kutilmoqda" not in line.lower()
            ]

            status_line = f"\n\n<b>Holati: {status_emoji} {status_text}!</b>"
            updated_text = f"{status_emoji} <b>Bron So'rovi Natijasi</b>\n\n" + "\n".join(filtered_lines).strip() + status_line

            # Edit message to remove inline buttons
            bot_views.edit_telegram_message(chat_id, message_id, updated_text, reply_markup={"inline_keyboard": []})

            # Answer callback query to remove spinner loading state
            bot_views.answer_callback_query(query_id, text=f"Bron muvaffaqiyatli {status_text.lower()}! {status_emoji}")

        except Exception as e:
            logger.error(f"Exception handling callback query: {e}", exc_info=True)
            import telegram_bot.views as bot_views
            bot_views.answer_callback_query(query_id, text="Tizimda xatolik yuz berdi. Iltimos qayta urining.", show_alert=True)
