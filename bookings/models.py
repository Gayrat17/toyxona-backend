from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from venues.models import Bar, Decoration, Package, Shift, WeddingHall


class BaseBooking(models.Model):
    """Common fields shared by hall and bar bookings."""

    class Status(models.TextChoices):
        HOLD = "HOLD", "Hold"
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="%(class)s_bookings",
    )
    date = models.DateField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    is_deposit_paid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField(null=True, blank=True)
    meeting_date = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @property
    def remaining_amount(self) -> Decimal:
        """Amount still due after the deposit."""

        return self.total_price - self.deposit_amount


class HallBooking(BaseBooking):
    """A wedding-hall booking for one date and shift."""

    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name="hall_bookings")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="hall_bookings")
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="hall_bookings")
    decoration = models.ForeignKey(
        Decoration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hall_bookings",
    )

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["hall", "date", "shift", "status"], name="hall_booking_availability_idx"),
            models.Index(fields=["user", "created_at"], name="hall_booking_user_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_price__gte=0),
                name="hall_booking_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__gte=0),
                name="hall_booking_deposit_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__lte=models.F("total_price")),
                name="hall_booking_deposit_lte_total",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.shift_id and self.hall_id:
            shift_hall_id = Shift.objects.filter(pk=self.shift_id).values_list(
                "hall_id", flat=True
            ).first()
            if shift_hall_id and shift_hall_id != self.hall_id:
                raise ValidationError({"shift": "Tanlangan smena ushbu zalga tegishli emas."})
        if self.package_id and self.hall_id:
            package_hall_id = Package.objects.filter(pk=self.package_id).values_list(
                "hall_id", flat=True
            ).first()
            if package_hall_id and package_hall_id != self.hall_id:
                raise ValidationError({"package": "Tanlangan paket ushbu zalga tegishli emas."})
        if self.decoration_id and self.hall_id:
            decoration_hall_id = Decoration.objects.filter(pk=self.decoration_id).values_list(
                "hall_id", flat=True
            ).first()
            if decoration_hall_id and decoration_hall_id != self.hall_id:
                raise ValidationError({"decoration": "Tanlangan dekoratsiya ushbu zalga tegishli emas."})

    def __str__(self) -> str:
        return f"Hall: {self.hall.name} - Date: {self.date} - User: {self.user.phone_number}"


class BarBooking(BaseBooking):
    """An hourly booking for a bar."""

    bar = models.ForeignKey(Bar, on_delete=models.CASCADE, related_name="bar_bookings")
    start_time = models.TimeField()
    end_time = models.TimeField()
    guest_count = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["bar", "date", "start_time", "end_time", "status"], name="bar_booking_availability_idx"),
            models.Index(fields=["user", "created_at"], name="bar_booking_user_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_price__gte=0),
                name="bar_booking_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__gte=0),
                name="bar_booking_deposit_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__lte=models.F("total_price")),
                name="bar_booking_deposit_lte_total",
            ),
            models.CheckConstraint(
                condition=Q(start_time__lt=models.F("end_time")),
                name="bar_booking_start_before_end",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "Chiqish vaqti kirish vaqtidan keyin bo'lishi shart."})

    def __str__(self) -> str:
        return f"Bar: {self.bar.name} - Date: {self.date} - Slot: {self.start_time}-{self.end_time}"
