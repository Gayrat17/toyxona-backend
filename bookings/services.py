"""Transactional booking and availability helpers.

All API booking writes go through these helpers.  Serializer validation is useful
for friendly errors, but it is not enough on its own: two requests can validate at
the same time.  The venue row is therefore locked while the final availability
check and write are performed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from venues.models import Bar, ShiftBlock, WeddingHall
from .models import BarBooking, BaseBooking, HallBooking


ACTIVE_BOOKING_STATUSES = (
    BaseBooking.Status.PENDING,
    BaseBooking.Status.CONFIRMED,
)


# A cancelled/rejected booking is terminal.  This makes Telegram callback
# retries idempotent and prevents a stale button from resurrecting a booking.
ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    BaseBooking.Status.PENDING: frozenset(
        {
            BaseBooking.Status.HOLD,
            BaseBooking.Status.CONFIRMED,
            BaseBooking.Status.REJECTED,
            BaseBooking.Status.CANCELLED,
        }
    ),
    BaseBooking.Status.HOLD: frozenset(
        {
            BaseBooking.Status.CONFIRMED,
            BaseBooking.Status.REJECTED,
            BaseBooking.Status.CANCELLED,
        }
    ),
    BaseBooking.Status.CONFIRMED: frozenset({BaseBooking.Status.CANCELLED}),
    BaseBooking.Status.REJECTED: frozenset(),
    BaseBooking.Status.CANCELLED: frozenset(),
}


def get_active_booking_q_filter(now=None) -> Q:
    """Return the query used everywhere to determine whether a booking is busy."""

    now = now or timezone.now()
    return (
        Q(status__in=ACTIVE_BOOKING_STATUSES)
        | Q(status=BaseBooking.Status.HOLD, expires_at__gt=now)
        # A manually-created HOLD without an expiry is treated as active.  This
        # is safer than allowing a potentially forgotten hold to be booked over.
        | Q(status=BaseBooking.Status.HOLD, expires_at__isnull=True)
    )


def _raise_conflict(message: str) -> None:
    raise ValidationError(message)


def assert_hall_available(
    *, hall_id: int,
    shift_id: int,
    booking_date: date,
    exclude_id: Optional[int] = None,
) -> None:
    """Check a hall shift and its admin block in one reusable place."""

    conflicts = HallBooking.objects.filter(
        hall_id=hall_id,
        shift_id=shift_id,
        date=booking_date,
    ).filter(get_active_booking_q_filter())
    if exclude_id is not None:
        conflicts = conflicts.exclude(pk=exclude_id)
    if conflicts.exists():
        _raise_conflict("Ushbu sana va smenada faol band qilingan bron mavjud.")

    if ShiftBlock.objects.filter(
        hall_id=hall_id,
        shift_id=shift_id,
        date=booking_date,
    ).exists():
        _raise_conflict("Ushbu sana va smena admin tomonidan yopib qo'yilgan (bloklangan).")


def assert_bar_available(
    *,
    bar_id: int,
    booking_date: date,
    start_time,
    end_time,
    exclude_id: Optional[int] = None,
) -> None:
    """Check overlapping active hourly bar bookings."""

    conflicts = BarBooking.objects.filter(
        bar_id=bar_id,
        date=booking_date,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).filter(get_active_booking_q_filter())
    if exclude_id is not None:
        conflicts = conflicts.exclude(pk=exclude_id)
    if conflicts.exists():
        _raise_conflict("Ushbu vaqt oralig'i boshqa bron bilan kesishmoqda.")


def validate_status_transition(current: str, requested: str) -> None:
    """Validate a booking state transition, allowing idempotent same-state writes."""

    if current == requested:
        return
    if requested not in ALLOWED_STATUS_TRANSITIONS.get(current, frozenset()):
        raise ValidationError(
            {"status": f"{current} holatidan {requested} holatiga o'tish mumkin emas."}
        )


def _booking_model_and_venue(booking: BaseBooking):
    if isinstance(booking, HallBooking):
        return HallBooking, WeddingHall, booking.hall_id
    if isinstance(booking, BarBooking):
        return BarBooking, Bar, booking.bar_id
    raise TypeError(f"Unsupported booking model: {type(booking)!r}")


def update_booking_status(booking: BaseBooking, new_status: str) -> BaseBooking:
    """Atomically update a booking status and re-check availability.

    This is used by the Telegram bot and can also be used by future admin/API
    actions.  Locking the venue before the booking gives status changes and new
    booking creation a consistent lock order.
    """

    model_cls, venue_cls, venue_id = _booking_model_and_venue(booking)
    with transaction.atomic():
        venue_cls.objects.select_for_update().get(pk=venue_id)
        locked = model_cls.objects.select_for_update().get(pk=booking.pk)
        validate_status_transition(locked.status, new_status)
        if (
            locked.status == BaseBooking.Status.HOLD
            and locked.expires_at is not None
            and locked.expires_at <= timezone.now()
            and new_status == BaseBooking.Status.CONFIRMED
        ):
            raise ValidationError({"status": "HOLD muddati tugagan, bronni tasdiqlab bo'lmaydi."})

        if new_status in ACTIVE_BOOKING_STATUSES or new_status == BaseBooking.Status.HOLD:
            if isinstance(locked, HallBooking):
                assert_hall_available(
                    hall_id=locked.hall_id,
                    shift_id=locked.shift_id,
                    booking_date=locked.date,
                    exclude_id=locked.pk,
                )
            else:
                assert_bar_available(
                    bar_id=locked.bar_id,
                    booking_date=locked.date,
                    start_time=locked.start_time,
                    end_time=locked.end_time,
                    exclude_id=locked.pk,
                )

        now = timezone.now()
        locked.status = new_status
        if new_status == BaseBooking.Status.HOLD:
            locked.expires_at = now + timedelta(hours=24)
        else:
            locked.expires_at = None
        locked.save(update_fields=["status", "expires_at"])
        return locked


def cancel_booking(booking: BaseBooking) -> BaseBooking:
    """Cancel a booking while retaining it for an audit trail."""

    return update_booking_status(booking, BaseBooking.Status.CANCELLED)


def validate_model_clean(instance: models.Model) -> None:
    """Convert model-level validation errors into DRF validation errors."""

    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
