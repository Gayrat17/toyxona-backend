from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_expired_holds():
    """
    Periodic task to clean up expired offline booking holds.
    Finds bookings with HOLD status where expires_at has passed and cancels them.
    """
    from bookings.models import HallBooking, BarBooking

    now = timezone.now()

    # Expire Hall bookings
    expired_halls = HallBooking.objects.filter(status='HOLD', expires_at__lt=now)
    halls_count = expired_halls.update(status='CANCELLED')

    # Expire Bar bookings
    expired_bars = BarBooking.objects.filter(status='HOLD', expires_at__lt=now)
    bars_count = expired_bars.update(status='CANCELLED')

    result_msg = f"Cleaned up expired holds: Hall bookings = {halls_count}, Bar bookings = {bars_count}"
    logger.info(result_msg)
    return result_msg
