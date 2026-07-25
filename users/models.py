from typing import Optional, Any
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models import EmailField, CharField, BooleanField, BigIntegerField
from django.db.models.enums import TextChoices


class CustomUserManager(BaseUserManager):
    """
    Custom user manager where phone_number is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(
        self, 
        phone_number: str, 
        password: Optional[str] = None, 
        **extra_fields: Any
    ) -> 'User':
        if not phone_number:
            raise ValueError('Telefon raqami kiritilishi shart')
        extra_fields.setdefault('is_active', True)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, 
        phone_number: str, 
        password: Optional[str] = None, 
        **extra_fields: Any
    ) -> 'User':
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser is_staff=True bo\'lishi shart.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser is_superuser=True bo\'lishi shart.')

        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model representing clients, venue owners, and admins.
    """
    class Role(TextChoices):
        CLIENT = "CLIENT", "Client"
        VENUE_OWNER = "VENUE_OWNER", "Venue Owner"
        ADMIN = "ADMIN", "Admin"

    username = None
    email = EmailField(blank=True, null=True)
    phone_number = CharField(max_length=20, unique=True)
    role = CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    is_verified = BooleanField(default=False)
    telegram_chat_id = BigIntegerField(blank=True, null=True, unique=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return f"{self.phone_number} ({self.get_role_display()})"

