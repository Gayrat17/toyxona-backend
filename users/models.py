from __future__ import annotations

import re
from typing import Any, Optional

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.enums import TextChoices


def normalize_phone_number(value: str) -> str:
    """Normalize common Uzbek phone formats to one canonical E.164 value.

    ``+998901234567``, ``998901234567``, ``0901234567`` and the local
    nine-digit form all resolve to ``+998901234567``.  Other international
    numbers are kept as ``+<digits>`` when they look like a valid E.164 number.
    """

    if value is None:
        raise ValueError("Telefon raqami kiritilishi shart")
    raw = str(value).strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise ValueError("Telefon raqami faqat raqamlardan iborat bo'lishi kerak")

    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = f"998{digits}"
    elif len(digits) == 10 and digits.startswith("0"):
        digits = f"998{digits[1:]}"

    if not 7 <= len(digits) <= 15:
        raise ValueError("Telefon raqami noto'g'ri uzunlikda")
    return f"+{digits}"


class CustomUserManager(BaseUserManager):
    """User manager using a normalized phone number as the login identifier."""

    def create_user(
        self,
        phone_number: str,
        password: Optional[str] = None,
        **extra_fields: Any,
    ) -> "User":
        try:
            phone_number = normalize_phone_number(phone_number)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        extra_fields.setdefault("is_active", True)
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        phone_number: str,
        password: Optional[str] = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser is_staff=True bo'lishi shart.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser is_superuser=True bo'lishi shart.")

        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractUser):
    """Client, venue owner, or platform administrator account."""

    class Role(TextChoices):
        CLIENT = "CLIENT", "Client"
        VENUE_OWNER = "VENUE_OWNER", "Venue Owner"
        ADMIN = "ADMIN", "Admin"

    username = None
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    is_verified = models.BooleanField(default=False)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True, unique=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        indexes = [models.Index(fields=["role", "is_active"], name="user_role_active_idx")]

    def clean(self) -> None:
        super().clean()
        if self.phone_number:
            self.phone_number = normalize_phone_number(self.phone_number)

    def save(self, *args, **kwargs):
        if self.phone_number:
            self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.phone_number} ({self.get_role_display()})"
