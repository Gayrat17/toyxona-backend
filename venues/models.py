from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from venues.utils import convert_image_field_to_webp


class Region(models.Model):
    """A first-level administrative region (viloyat/shahar)."""

    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Viloyat"
        verbose_name_plural = "Viloyatlar"
        indexes = [models.Index(fields=["order", "name"], name="region_order_name_idx")]

    def __str__(self) -> str:
        return self.name


class District(models.Model):
    """A district belonging to a region."""

    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="districts")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Tuman"
        verbose_name_plural = "Tumanlar"
        constraints = [
            models.UniqueConstraint(
                fields=["region", "name"],
                name="district_region_name_unique",
            ),
        ]
        indexes = [models.Index(fields=["region", "order"], name="district_region_order_idx")]

    def __str__(self) -> str:
        return f"{self.region.name} - {self.name}"


class _Venue(models.Model):
    """Shared fields for venues; concrete venue models inherit these fields."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    description = models.TextField()
    cover_image = models.ImageField(upload_to="venues/covers/", null=True, blank=True)
    video_url = models.URLField(blank=True, null=True)
    map_link = models.URLField(blank=True, null=True)
    amenities = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        if self.region_id and self.district_id:
            district_region_id = District.objects.filter(pk=self.district_id).values_list(
                "region_id", flat=True
            ).first()
            if district_region_id and district_region_id != self.region_id:
                raise ValidationError({"district": "Tuman tanlangan viloyatga tegishli emas."})


class WeddingHall(_Venue):
    """A wedding hall rented by shift."""

    # The related name is defined here instead of on the abstract base so the
    # public API keeps the existing ``user.wedding_halls`` contract.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wedding_halls",
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wedding_halls",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wedding_halls",
    )
    max_capacity = models.PositiveIntegerField()
    required_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["region", "district"], name="hall_region_district_idx"),
            models.Index(fields=["owner", "created_at"], name="hall_owner_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(required_deposit__gte=0),
                name="hall_required_deposit_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Bar(_Venue):
    """A bar rented by an hourly time interval."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bars",
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bars",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bars",
    )
    capacity = models.PositiveIntegerField()
    price_per_hour = models.DecimalField(max_digits=12, decimal_places=2)
    required_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=1000000)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["region", "district"], name="bar_region_district_idx"),
            models.Index(fields=["owner", "created_at"], name="bar_owner_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_per_hour__gte=0),
                name="bar_price_per_hour_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(required_deposit__gte=0),
                name="bar_required_deposit_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Media(models.Model):
    """An image or video in a venue gallery."""

    MEDIA_TYPES = (
        ("image", "Rasm"),
        ("video", "Video"),
    )

    hall = models.ForeignKey(
        WeddingHall,
        on_delete=models.CASCADE,
        related_name="gallery_images",
        verbose_name="Wedding Hall",
        null=True,
        blank=True,
    )
    bar = models.ForeignKey(
        Bar,
        on_delete=models.CASCADE,
        related_name="gallery_images",
        verbose_name="Bar",
        null=True,
        blank=True,
    )
    file = models.FileField(upload_to="venues/media/", null=True, blank=True)
    image = models.ImageField(upload_to="venues/gallery/", null=True, blank=True)
    type = models.CharField(max_length=10, choices=MEDIA_TYPES, default="image")
    is_main = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Mahsulot media"
        verbose_name_plural = "Mahsulot medialari"
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(hall__isnull=False) & Q(bar__isnull=True))
                    | (Q(hall__isnull=True) & Q(bar__isnull=False))
                ),
                name="media_exactly_one_venue",
            ),
        ]
        indexes = [
            models.Index(fields=["hall", "position"], name="media_hall_position_idx"),
            models.Index(fields=["bar", "position"], name="media_bar_position_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        if bool(self.hall_id) == bool(self.bar_id):
            raise ValidationError("Media faqat bitta zal yoki bitta bar bilan bog'lanishi kerak.")
        if self.type == "image" and not (self.image or self.file):
            raise ValidationError({"image": "Rasm fayli kiritilishi shart."})
        if self.type == "video" and not self.file:
            raise ValidationError({"file": "Video fayli kiritilishi shart."})

    def save(self, *args, **kwargs):
        # Uploaded gallery images are normalized once at the model boundary so
        # files created by admin/scripts get the same treatment as API uploads.
        if self.type == "image":
            if self.file:
                convert_image_field_to_webp(self.file)
            if self.image:
                convert_image_field_to_webp(self.image)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        venue_name = self.hall.name if self.hall else (self.bar.name if self.bar else "Venue")
        return f"Media for {venue_name} ({self.id})"


# Alias kept for older imports and clients.
VenueImage = Media


class Shift(models.Model):
    """A named operating shift for a wedding hall."""

    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name="shifts")
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_time", "id"]
        constraints = [
            models.UniqueConstraint(fields=["hall", "name"], name="shift_hall_name_unique"),
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")),
                name="shift_start_before_end",
            ),
        ]
        indexes = [models.Index(fields=["hall", "is_active"], name="shift_hall_active_idx")]

    def clean(self) -> None:
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "Tugash vaqti boshlanish vaqtidan keyin bo'lishi shart."})

    def __str__(self) -> str:
        return f"{self.hall.name} - {self.name} ({self.start_time}-{self.end_time})"


class Package(models.Model):
    """A wedding hall package priced for a guest count."""

    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name="packages")
    guest_count = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()

    class Meta:
        ordering = ["guest_count", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["hall", "guest_count"],
                name="package_hall_guest_count_unique",
            ),
            models.CheckConstraint(condition=Q(price__gte=0), name="package_price_nonnegative"),
        ]
        indexes = [models.Index(fields=["hall", "guest_count"], name="package_hall_guests_idx")]

    def clean(self) -> None:
        super().clean()
        if self.hall_id and self.guest_count:
            capacity = WeddingHall.objects.filter(pk=self.hall_id).values_list(
                "max_capacity", flat=True
            ).first()
            if capacity and self.guest_count > capacity:
                raise ValidationError({"guest_count": "Mehmonlar soni zal sig'imidan oshmasligi kerak."})

    def __str__(self) -> str:
        return f"{self.hall.name} - {self.guest_count} kishilik ({self.price} UZS)"


class Decoration(models.Model):
    """An optional decoration add-on for a wedding hall."""

    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name="decorations")
    name = models.CharField(max_length=255)
    additional_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(additional_price__gte=0),
                name="decoration_price_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.hall.name} - {self.name} (+{self.additional_price} UZS)"


class ShiftBlock(models.Model):
    """A shift unavailable on a particular date."""

    hall = models.ForeignKey(WeddingHall, on_delete=models.CASCADE, related_name="shift_blocks")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="shift_blocks")
    date = models.DateField()
    reason = models.CharField(max_length=255)

    class Meta:
        ordering = ["date", "shift_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["hall", "shift", "date"],
                name="shift_block_hall_shift_date_unique",
            ),
        ]
        indexes = [models.Index(fields=["hall", "date"], name="block_hall_date_idx")]

    def clean(self) -> None:
        super().clean()
        if self.hall_id and self.shift_id:
            shift_hall_id = Shift.objects.filter(pk=self.shift_id).values_list(
                "hall_id", flat=True
            ).first()
            if shift_hall_id and shift_hall_id != self.hall_id:
                raise ValidationError({"shift": "Tanlangan smena ushbu zalga tegishli emas."})

    def __str__(self) -> str:
        return f"{self.hall.name} - {self.shift.name} - {self.date} (Yopilgan: {self.reason})"
