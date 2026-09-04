import logging
from typing import Any

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from kombu.exceptions import OperationalError

from .models import BarBooking, BaseBooking, HallBooking
from telegram_bot.tasks import send_new_booking_notification

logger = logging.getLogger(__name__)


def _trigger_booking_notification(booking_type: str, booking_id: int) -> None:
    """Queue a notification only after the booking transaction commits."""

    def dispatch() -> None:
        try:
            if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                send_new_booking_notification.delay(booking_type, booking_id)
            else:
                # Do not wait for Redis retries during an HTTP request and do
                # not create result-backend entries for fire-and-forget alerts.
                send_new_booking_notification.apply_async(
                    args=(booking_type, booking_id), ignore_result=True, retry=False
                )
        except OperationalError as exc:
            # A notification broker outage must not roll back a booking or
            # flood application logs with a transport traceback.
            logger.warning(
                "Could not dispatch booking notification type=%s id=%s: %s",
                booking_type,
                booking_id,
                exc,
            )
        except Exception:
            # Notifications must never roll back a successful booking.
            logger.exception(
                "Could not dispatch booking notification type=%s id=%s",
                booking_type,
                booking_id,
            )

    transaction.on_commit(dispatch)


@receiver(post_save, sender=HallBooking)
def notify_hall_owner_on_booking_creation(
    sender: Any, instance: HallBooking, created: bool, **kwargs: Any
) -> None:
    if created and instance.status == BaseBooking.Status.PENDING:
        _trigger_booking_notification("hall", instance.pk)


@receiver(post_save, sender=BarBooking)
def notify_bar_owner_on_booking_creation(
    sender: Any, instance: BarBooking, created: bool, **kwargs: Any
) -> None:
    if created and instance.status == BaseBooking.Status.PENDING:
        _trigger_booking_notification("bar", instance.pk)
