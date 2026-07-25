from decimal import Decimal
from django.db.models import (
    CASCADE, ForeignKey, TimeField, PositiveIntegerField, SET_NULL, DecimalField, DateField,
    BooleanField, CharField, DateTimeField, TextField, Model, TextChoices
)

from venues.models import WeddingHall, Bar, Shift, Package, Decoration


class BaseBooking(Model):
    """
    Abstract booking model containing common fields for both halls and bars.
    """
    class Status(TextChoices):
        HOLD = "HOLD", "Hold"
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    user = ForeignKey("users.User", CASCADE, related_name='%(class)s_bookings')
    date = DateField()
    total_price = DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    is_deposit_paid = BooleanField(default=False)
    status = CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    expires_at = DateTimeField(null=True, blank=True)  # Used for HOLD status expiration
    meeting_date = DateTimeField(null=True, blank=True)  # Offline negotiation date
    admin_notes = TextField(null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @property
    def remaining_amount(self) -> Decimal:
        """
        Calculates the remaining unpaid amount.
        """
        return self.total_price - self.deposit_amount


class HallBooking(BaseBooking):
    """
    Booking representation for Wedding Halls, including shifts, packages, and decorations.
    """
    hall = ForeignKey(WeddingHall, CASCADE, related_name='hall_bookings')
    shift = ForeignKey(Shift, CASCADE, related_name='hall_bookings')
    package = ForeignKey(Package, CASCADE, related_name='hall_bookings')
    decoration = ForeignKey(Decoration, SET_NULL, null=True, blank=True, related_name='hall_bookings')

    def __str__(self) -> str:
        return f"Hall: {self.hall.name} - Date: {self.date} - User: {self.user.phone_number}"


class BarBooking(BaseBooking):
    """
    Booking representation for Bars, containing hourly slots.
    """
    bar = ForeignKey(Bar, CASCADE, related_name='bar_bookings')
    start_time = TimeField()
    end_time = TimeField()
    guest_count = PositiveIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Bar: {self.bar.name} - Date: {self.date} - Slot: {self.start_time}-{self.end_time}"

