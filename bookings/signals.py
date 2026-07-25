import sys
import logging
from typing import Any
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import HallBooking, BarBooking, BaseBooking
from telegram_bot.tasks import send_new_booking_notification

logger = logging.getLogger(__name__)


def _trigger_booking_notification(booking_type: str, booking_id: int) -> None:
    """Helper to dispatch booking notification synchronously or via Celery safely."""
    logger.info(f"New booking notification dispatching for type={booking_type}, id={booking_id}")
    is_testing_or_debug = (
        'test' in sys.argv 
        or getattr(settings, 'DEBUG', False) 
        or getattr(settings, 'TESTING', False)
        or getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
    )
    
    if is_testing_or_debug:
        try:
            send_new_booking_notification(booking_type, booking_id)
        except Exception as e:
            logger.warning(f"Failed synchronous notification execution ({booking_type} #{booking_id}): {e}")
    else:
        try:
            send_new_booking_notification.delay(booking_type, booking_id)
        except Exception as e:
            logger.error(f"Could not dispatch Celery task for booking notification ({booking_type} #{booking_id}): {e}")



@receiver(post_save, sender=HallBooking)
def notify_hall_owner_on_booking_creation(sender: Any, instance: HallBooking, created: bool, **kwargs: Any) -> None:
    """
    Sends a Telegram notification to the Wedding Hall owner when a booking is created (PENDING).
    """
    if created and instance.status == BaseBooking.Status.PENDING:
        _trigger_booking_notification('hall', instance.id)


@receiver(post_save, sender=BarBooking)
def notify_bar_owner_on_booking_creation(sender: Any, instance: BarBooking, created: bool, **kwargs: Any) -> None:
    """
    Sends a Telegram notification to the Bar owner when a booking is created (PENDING).
    """
    if created and instance.status == BaseBooking.Status.PENDING:
        _trigger_booking_notification('bar', instance.id)

