from unittest.mock import patch
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import TelegramAuthSession, User, normalize_phone_number
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

    def test_telegram_auth_lifecycle(self):
        client = APIClient()

        # 1. Init session
        init_resp = client.post("/api/v1/auth/telegram/init/")
        self.assertEqual(init_resp.status_code, 201)
        self.assertIn("session_id", init_resp.data)
        session_id = init_resp.data["session_id"]

        # 2. Check pending status
        status_resp = client.get(f"/api/v1/auth/telegram/status/{session_id}/")
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.data["status"], "PENDING")

        # 3. Simulate bot webhook receiving /start auth_<session_id>
        with patch("telegram_bot.services.send_telegram_message") as mock_send:
            mock_send.return_value = {"ok": True}
            webhook_start = client.post(
                "/api/v1/notifications/webhook/telegram/",
                {
                    "update_id": 1001,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 99887766},
                        "from": {"id": 99887766, "first_name": "Ali", "last_name": "Valiyev"},
                        "text": f"/start auth_{session_id}",
                    },
                },
                format="json",
            )
            self.assertEqual(webhook_start.status_code, 200)
            mock_send.assert_called()

        # 4. Simulate bot webhook receiving shared contact
        with patch("telegram_bot.services.send_telegram_message") as mock_send:
            mock_send.return_value = {"ok": True}
            webhook_contact = client.post(
                "/api/v1/notifications/webhook/telegram/",
                {
                    "update_id": 1002,
                    "message": {
                        "message_id": 2,
                        "chat": {"id": 99887766},
                        "from": {"id": 99887766, "first_name": "Ali", "last_name": "Valiyev"},
                        "contact": {
                            "phone_number": "+998901112233",
                            "first_name": "Ali",
                            "user_id": 99887766,
                        },
                    },
                },
                format="json",
            )
            self.assertEqual(webhook_contact.status_code, 200)

        # 5. Check authenticated status on website
        status_auth = client.get(f"/api/v1/auth/telegram/status/{session_id}/")
        self.assertEqual(status_auth.status_code, 200)
        self.assertEqual(status_auth.data["status"], "AUTHENTICATED")
        self.assertTrue(status_auth.data["is_new_user"])
        self.assertIn("access", status_auth.data)
        self.assertIn("refresh", status_auth.data)
        self.assertEqual(status_auth.data["user"]["phone_number"], "+998901112233")

        # 6. Replay attack prevention: second call should be COMPLETED
        replay_resp = client.get(f"/api/v1/auth/telegram/status/{session_id}/")
        self.assertEqual(replay_resp.status_code, 400)
        self.assertEqual(replay_resp.data["status"], "COMPLETED")

        # 7. Complete profile (set role to VENUE_OWNER)
        access_token = status_auth.data["access"]
        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        profile_resp = auth_client.post(
            "/api/v1/auth/complete-profile/",
            {"role": "VENUE_OWNER", "first_name": "Alisher"},
            format="json",
        )
        self.assertEqual(profile_resp.status_code, 200)
        self.assertEqual(profile_resp.data["user"]["role"], "VENUE_OWNER")
        self.assertEqual(profile_resp.data["user"]["first_name"], "Alisher")

