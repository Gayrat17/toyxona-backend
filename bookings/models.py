from django.db import models
from django.conf import settings
from venues.models import WeddingHall, Bar, Shift, Package, Decoration

class BaseBooking(models.Model):
    """
    Abstract booking model containing common fields for both halls and bars.
    """
    STATUS_CHOICES = (
        ('HOLD', 'Muzlatilgan (Hold)'),
        ('PENDING', 'Kutilmoqda (Pending)'),
        ('CONFIRMED', 'Tasdiqlangan (Confirmed)'),
        ('REJECTED', 'Rad etilgan (Rejected)'),
        ('CANCELLED', 'Bekor qilingan (Cancelled)'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='%(class)s_bookings')
    date = models.DateField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_deposit_paid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    expires_at = models.DateTimeField(null=True, blank=True)  # Used for HOLD status expiration
    meeting_date = models.DateTimeField(null=True, blank=True)  # Offline negotiation date
    admin_notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @property
    def remaining_amount(self):
        """
        Calculates the remaining unpaid amount.
        """
        return self.total_price - self.deposit_amount

class HallBooking(BaseBooking):
    """
    Booking representation for Wedding Halls, including shifts, packages, and decorations.
    """
    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name='hall_bookings')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='hall_bookings')
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='hall_bookings')
    decoration = models.ForeignKey(Decoration, on_delete=models.SET_NULL, null=True, blank=True, related_name='hall_bookings')

    def __str__(self):
        return f"Hall: {self.hall.name} - Date: {self.date} - User: {self.user.phone_number}"

class BarBooking(BaseBooking):
    """
    Booking representation for Bars, containing hourly slots.
    """
    bar = models.ForeignKey(Bar, on_delete=models.CASCADE, related_name='bar_bookings')
    start_time = models.TimeField()
    end_time = models.TimeField()
    guest_count = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Bar: {self.bar.name} - Date: {self.date} - Slot: {self.start_time}-{self.end_time}"
