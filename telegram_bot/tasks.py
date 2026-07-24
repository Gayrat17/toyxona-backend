from celery import shared_task
import logging
from telegram_bot.services import send_telegram_message

logger = logging.getLogger(__name__)

@shared_task
def send_telegram_notification(chat_id, message):
    """
    Fallback task for simple HTML message notifications.
    """
    res = send_telegram_message(chat_id, message)
    return "SUCCESS" if res.get("ok") else f"FAILED: {res.get('description')}"

@shared_task
def send_new_booking_notification(booking_type, booking_id):
    """
    Sends a beautifully formatted booking request notification to the venue owner.
    """
    from bookings.models import HallBooking, BarBooking
    from django.utils.html import escape

    try:
        if booking_type == 'hall':
            booking = HallBooking.objects.select_related('hall', 'hall__owner', 'shift', 'user').get(id=booking_id)
            venue_name = booking.hall.name
            owner = booking.hall.owner
            shift_name = booking.shift.name
            details = f"⏰ <b>Smena:</b> {escape(shift_name)}"
        elif booking_type == 'bar':
            booking = BarBooking.objects.select_related('bar', 'bar__owner', 'user').get(id=booking_id)
            venue_name = booking.bar.name
            owner = booking.bar.owner
            start_formatted = booking.start_time.strftime('%H:%M')
            end_formatted = booking.end_time.strftime('%H:%M')
            details = f"⏰ <b>Vaqt:</b> {start_formatted} - {end_formatted}"
        else:
            logger.error(f"Unknown booking type: {booking_type}")
            return "UNKNOWN_BOOKING_TYPE"

        # Owner va Chat ID qat'iy tekshiruvi
        if not owner.telegram_chat_id:
            warning_msg = f"[BOT WARNING] Xabar yuborilmadi! Joy egasida (User ID: {owner.id}, Phone: {owner.phone_number}) telegram_chat_id yo'q. U avval botga girib /start bosishi kerak!"
            print(warning_msg)
            logger.warning(warning_msg)
            return "OWNER_NO_TELEGRAM"

        # Format currency nicely
        total_formatted = f"{int(booking.total_price):,}".replace(",", " ")
        deposit_formatted = f"{int(booking.deposit_amount):,}".replace(",", " ")
        client_name = f"{booking.user.first_name or ''} {booking.user.last_name or ''}".strip() or "Mijoz"

        # Escape dynamic text values to prevent HTML parsing errors on Telegram side
        venue_name_escaped = escape(venue_name)
        client_name_escaped = escape(client_name)
        phone_escaped = escape(booking.user.phone_number)

        message = (
            f"📥 <b>Yangi Bron So'rovi! (Kutilmoqda)</b>\n\n"
            f"🏢 <b>Joy nomi:</b> {venue_name_escaped} ({booking_type.upper()})\n"
            f"📅 <b>Sana:</b> {booking.date}\n"
            f"{details}\n"
            f"👤 <b>Mijoz:</b> {client_name_escaped}\n"
            f"📞 <b>Telefon:</b> {phone_escaped}\n"
            f"💰 <b>Jami summa:</b> {total_formatted} UZS\n"
            f"💵 <b>Zakalat miqdori:</b> {deposit_formatted} UZS\n\n"
            f"📞 <i>Mijoz bilan bog'lanib, oflayn uchrashuv belgilang!</i>"
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Tasdiqlash", "callback_data": f"confirm_booking_{booking_type}_{booking.id}"},
                    {"text": "❌ Rad etish", "callback_data": f"reject_booking_{booking_type}_{booking.id}"}
                ]
            ]
        }

        res = send_telegram_message(owner.telegram_chat_id, message, reply_markup=reply_markup)
        if res.get("ok"):
            return "SUCCESS"
        else:
            return f"FAILED: {res.get('description')}"

    except (HallBooking.DoesNotExist, BarBooking.DoesNotExist):
        logger.error(f"Booking {booking_type} with ID {booking_id} not found.")
        return "BOOKING_NOT_FOUND"
    except Exception as e:
        logger.exception(f"Error sending booking notification: {e}")
        return f"ERROR: {str(e)}"
