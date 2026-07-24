from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    """
    Custom user manager where phone_number is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Telefon raqami kiritilishi shart')
        extra_fields.setdefault('is_active', True)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser is_staff=True bo\'lishi shart.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser is_superuser=True bo\'lishi shart.')

        return self.create_user(phone_number, password, **extra_fields)

class User(AbstractUser):
    """
    Custom user model representing clients, venue owners, and admins.
    """
    ROLE_CHOICES = (
        ('CLIENT', 'Mijoz (Client)'),
        ('VENUE_OWNER', 'Joy Egasi (Venue Owner)'),
        ('ADMIN', 'Platforma Admini (Admin)'),
    )

    username = None
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    is_verified = models.BooleanField(default=False)
    telegram_chat_id = models.BigIntegerField(blank=True, null=True, unique=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.phone_number} ({self.get_role_display()})"
