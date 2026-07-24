from django.db import models
from django.conf import settings

class WeddingHall(models.Model):
    """
    Model representing wedding halls, rented by shift with custom packages and decorations.
    """
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wedding_halls')
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    description = models.TextField()
    max_capacity = models.PositiveIntegerField()
    required_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=5000000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Bar(models.Model):
    """
    Model representing bars, rented by the hour.
    """
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bars')
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    description = models.TextField()
    capacity = models.PositiveIntegerField()
    price_per_hour = models.DecimalField(max_digits=12, decimal_places=2)
    required_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=1000000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Shift(models.Model):
    """
    Shifts for wedding halls (e.g. Lunch/Dinner).
    """
    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name='shifts')
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('hall', 'name')

    def __str__(self):
        return f"{self.hall.name} - {self.name} ({self.start_time}-{self.end_time})"

class Package(models.Model):
    """
    Pricing packages based on guest count for a wedding hall.
    """
    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name='packages')
    guest_count = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()

    class Meta:
        unique_together = ('hall', 'guest_count')

    def __str__(self):
        return f"{self.hall.name} - {self.guest_count} kishilik ({self.price} UZS)"

class Decoration(models.Model):
    """
    Optional decoration choices for a wedding hall.
    """
    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name='decorations')
    name = models.CharField(max_length=255)
    additional_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.hall.name} - {self.name} (+{self.additional_price} UZS)"

class ShiftBlock(models.Model):
    """
    Blocks specific shifts on specific dates for a wedding hall.
    """
    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name='shift_blocks')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='shift_blocks')
    date = models.DateField()
    reason = models.CharField(max_length=255)

    class Meta:
        unique_together = ('hall', 'shift', 'date')

    def __str__(self):
        return f"{self.hall.name} - {self.shift.name} - {self.date} (Yopilgan: {self.reason})"
