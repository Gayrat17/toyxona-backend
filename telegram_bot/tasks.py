import logging

from celery import shared_task
from django.utils.html import escape

from telegram_bot.services import send_telegram_message

logger = logging.getLogger(__name__)


@shared_task
def send_telegram_notification(chat_id: int, message: str) -> str:
    """Send a generic Telegram message and expose a useful task result."""

    result = send_telegram_message(chat_id, message)
    return "SUCCESS" if result.get("ok") else f"FAILED: {result.get('description')}"


@shared_task
def send_new_booking_notification(booking_type: str, booking_id: int) -> str:
    """Notify a venue owner about a newly-created pending booking."""

    from bookings.models import BarBooking, BaseBooking, HallBooking

    try:
        if booking_type == "hall":
            booking = HallBooking.objects.select_related(
                "hall__owner", "shift", "user"
            ).get(pk=booking_id)
            venue_name = booking.hall.name
            owner = booking.hall.owner
            details = f"⏰ <b>Smena:</b> {escape(booking.shift.name)}"
        elif booking_type == "bar":
            booking = BarBooking.objects.select_related("bar__owner", "user").get(pk=booking_id)
            venue_name = booking.bar.name
            owner = booking.bar.owner
            details = (
                f"⏰ <b>Vaqt:</b> {booking.start_time.strftime('%H:%M')} - "
                f"{booking.end_time.strftime('%H:%M')}"
            )
        else:
            logger.error("Unknown booking type: %s", booking_type)
            return "UNKNOWN_BOOKING_TYPE"

        if booking.status != BaseBooking.Status.PENDING:
            return "BOOKING_NOT_PENDING"
        if owner.telegram_chat_id is None:
            logger.warning(
                "Telegram notification skipped: owner_id=%s has no chat id", owner.pk
            )
            return "OWNER_NO_TELEGRAM"

        def format_money(value) -> str:
            return f"{int(value):,}".replace(",", " ")

        client_name = (
            f"{booking.user.first_name or ''} {booking.user.last_name or ''}".strip()
            or "Mijoz"
        )
        message = (
            "📥 <b>Yangi Bron So'rovi! (Kutilmoqda)</b>\n\n"
            f"🏢 <b>Joy nomi:</b> {escape(venue_name)} ({booking_type.upper()})\n"
            f"📅 <b>Sana:</b> {booking.date}\n"
            f"{details}\n"
            f"👤 <b>Mijoz:</b> {escape(client_name)}\n"
            f"📞 <b>Telefon:</b> {escape(booking.user.phone_number)}\n"
            f"💰 <b>Jami summa:</b> {format_money(booking.total_price)} UZS\n"
            f"💵 <b>Zakalat miqdori:</b> {format_money(booking.deposit_amount)} UZS\n\n"
            "📞 <i>Mijoz bilan bog'lanib, oflayn uchrashuv belgilang!</i>"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Tasdiqlash",
                        "callback_data": f"confirm_booking_{booking_type}_{booking.pk}",
                    },
                    {
                        "text": "❌ Rad etish",
                        "callback_data": f"reject_booking_{booking_type}_{booking.pk}",
                    },
                ]
            ]
        }
        result = send_telegram_message(
            owner.telegram_chat_id, message, reply_markup=reply_markup
        )
        return "SUCCESS" if result.get("ok") else f"FAILED: {result.get('description')}"
    except (HallBooking.DoesNotExist, BarBooking.DoesNotExist):
        logger.error("Booking %s #%s not found", booking_type, booking_id)
        return "BOOKING_NOT_FOUND"
    except Exception:
        logger.exception("Error sending notification for %s #%s", booking_type, booking_id)
        return "ERROR"
