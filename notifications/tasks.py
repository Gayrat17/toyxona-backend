import logging

from celery import shared_task
from django.utils import timezone

from bookings.models import BarBooking, BaseBooking, HallBooking

logger = logging.getLogger(__name__)


@shared_task
def check_expired_holds() -> dict[str, int]:
    """Cancel all expired holds and return counts for monitoring."""

    now = timezone.now()
    hall_count = HallBooking.objects.filter(
        status=BaseBooking.Status.HOLD,
        expires_at__lte=now,
    ).update(status=BaseBooking.Status.CANCELLED)
    bar_count = BarBooking.objects.filter(
        status=BaseBooking.Status.HOLD,
        expires_at__lte=now,
    ).update(status=BaseBooking.Status.CANCELLED)

    result = {"hall_bookings": hall_count, "bar_bookings": bar_count}
    logger.info("Expired booking holds cleaned up: %s", result)
    return result
