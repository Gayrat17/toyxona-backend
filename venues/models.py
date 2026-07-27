from django.conf import settings
from django.db.models import (
    Model, ForeignKey, CharField, TextField, ImageField, URLField, 
    DateTimeField, JSONField, PositiveIntegerField, CASCADE, SET_NULL, DecimalField, 
    BooleanField, FileField, DateField, TimeField
)

from venues.utils import convert_image_field_to_webp


class Region(Model):
    """
    Model representing regions (Viloyatlar).
    """
    name = CharField(max_length=100, unique=True)
    order = PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Viloyat"
        verbose_name_plural = "Viloyatlar"

    def __str__(self):
        return self.name


class District(Model):
    """
    Model representing districts (Tumanlar) within a region.
    """
    region = ForeignKey(Region, on_delete=CASCADE, related_name='districts')
    name = CharField(max_length=100)
    order = PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('region', 'name')
        verbose_name = "Tuman"
        verbose_name_plural = "Tumanlar"

    def __str__(self):
        return f"{self.region.name} - {self.name}"


class WeddingHall(Model):
    """
    Model representing wedding halls, rented by shift with custom packages and decorations.
    """
    owner = ForeignKey("users.User", on_delete=CASCADE, related_name='wedding_halls')
    region = ForeignKey(Region, on_delete=SET_NULL, null=True, blank=True, related_name='wedding_halls')
    district = ForeignKey(District, on_delete=SET_NULL, null=True, blank=True, related_name='wedding_halls')
    name = CharField(max_length=255)
    address = CharField(max_length=255)
    description = TextField()
    max_capacity = PositiveIntegerField()
    required_deposit = DecimalField(max_digits=12, decimal_places=2, default=0)
    cover_image = ImageField(upload_to='venues/covers/', null=True, blank=True)
    video_url = URLField(blank=True, null=True)
    map_link = URLField(blank=True, null=True)
    amenities = JSONField(default=list, blank=True)
    created_at = DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Bar(Model):
    """
    Model representing bars, rented by the hour.
    """
    owner = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='bars')
    region = ForeignKey(Region, on_delete=SET_NULL, null=True, blank=True, related_name='bars')
    district = ForeignKey(District, on_delete=SET_NULL, null=True, blank=True, related_name='bars')
    name = CharField(max_length=255)
    address = CharField(max_length=255)
    description = TextField()
    capacity = PositiveIntegerField()
    price_per_hour = DecimalField(max_digits=12, decimal_places=2)
    required_deposit = DecimalField(max_digits=12, decimal_places=2, default=1000000)
    cover_image = ImageField(upload_to='venues/covers/', null=True, blank=True)
    video_url = URLField(blank=True, null=True)
    map_link = URLField(blank=True, null=True)
    amenities = JSONField(default=list, blank=True)
    created_at = DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Media(Model):
    MEDIA_TYPES = (
        ("image", "Rasm"),
        ("video", "Video"),
    )
    hall = ForeignKey("venues.WeddingHall", CASCADE, related_name="gallery_images", verbose_name="Wedding Hall", null=True, blank=True)
    bar = ForeignKey("venues.Bar", CASCADE, related_name="gallery_images", verbose_name="Bar", null=True, blank=True)
    file = FileField(upload_to="venues/media/", null=True, blank=True)
    image = ImageField(upload_to="venues/gallery/", null=True, blank=True)
    type = CharField(max_length=10, choices=MEDIA_TYPES, default="image")
    is_main = BooleanField(default=False)
    position = PositiveIntegerField(default=0)
    created_at = DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Mahsulot media"
        verbose_name_plural = "Mahsulot medialari"
        ordering = ["position", "id"]

    def save(self, *args, **kwargs):
        if self.file and self.type == "image":
            convert_image_field_to_webp(self.file)
        if self.image:
            convert_image_field_to_webp(self.image)
        super().save(*args, **kwargs)

    def __str__(self):
        venue_name = self.hall.name if self.hall else (self.bar.name if self.bar else "Venue")
        return f"Media for {venue_name} ({self.id})"


# Alias VenueImage for backwards compatibility across imports
VenueImage = Media


class Shift(Model):
    """
    Shifts for wedding halls (e.g. Lunch/Dinner).
    """
    hall = ForeignKey(WeddingHall, on_delete=CASCADE, related_name='shifts')
    name = CharField(max_length=100)
    start_time = TimeField()
    end_time = TimeField()
    is_active = BooleanField(default=True)

    class Meta:
        unique_together = ('hall', 'name')

    def __str__(self):
        return f"{self.hall.name} - {self.name} ({self.start_time}-{self.end_time})"


class Package(Model):
    """
    Pricing packages based on guest count for a wedding hall.
    """
    hall = ForeignKey(WeddingHall, on_delete=CASCADE, related_name='packages')
    guest_count = PositiveIntegerField()
    price = DecimalField(max_digits=12, decimal_places=2)
    description = TextField()

    class Meta:
        unique_together = ('hall', 'guest_count')

    def __str__(self):
        return f"{self.hall.name} - {self.guest_count} kishilik ({self.price} UZS)"


class Decoration(Model):
    """
    Optional decoration choices for a wedding hall.
    """
    hall = ForeignKey(WeddingHall, on_delete=CASCADE, related_name='decorations')
    name = CharField(max_length=255)
    additional_price = DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.hall.name} - {self.name} (+{self.additional_price} UZS)"


class ShiftBlock(Model):
    """
    Blocks specific shifts on specific dates for a wedding hall.
    """
    hall = ForeignKey(WeddingHall, on_delete=CASCADE, related_name='shift_blocks')
    shift = ForeignKey(Shift, on_delete=CASCADE, related_name='shift_blocks')
    date = DateField()
    reason = CharField(max_length=255)

    class Meta:
        unique_together = ('hall', 'shift', 'date')

    def __str__(self):
        return f"{self.hall.name} - {self.shift.name} - {self.date} (Yopilgan: {self.reason})"
