from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import User, normalize_phone_number
from .serializers import UserCreateSerializer


class UserTests(TestCase):
    def test_common_uzbek_phone_formats_are_normalized(self):
        expected = "+998901234567"
        self.assertEqual(normalize_phone_number("90 123 45 67"), expected)
        self.assertEqual(normalize_phone_number("998901234567"), expected)
        self.assertEqual(normalize_phone_number("+998901234567"), expected)
        self.assertEqual(normalize_phone_number("0901234567"), expected)

        first = User.objects.create_user("90 123 45 67", password="strong-pass-1")
        self.assertEqual(first.phone_number, expected)
        with self.assertRaises(IntegrityError):
            User.objects.create_user("+998901234567", password="strong-pass-1")

    def test_jwt_login_accepts_local_phone_format(self):
        User.objects.create_user("+998901234570", password="strong-pass-1")
        response = APIClient().post(
            "/api/v1/auth/jwt/create/",
            {"phone_number": "0901234570", "password": "strong-pass-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_registration_cannot_create_admin(self):
        serializer = UserCreateSerializer(
            data={
                "phone_number": "+998901234568",
                "password": "strong-pass-1",
                "role": User.Role.ADMIN,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("role", serializer.errors)

    def test_registration_creates_a_hashed_password(self):
        serializer = UserCreateSerializer(
            data={
                "phone_number": "+998901234569",
                "password": "strong-pass-1",
                "role": User.Role.CLIENT,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertTrue(user.check_password("strong-pass-1"))
        self.assertNotEqual(user.password, "strong-pass-1")
