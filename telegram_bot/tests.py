from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from bookings.models import HallBooking, BarBooking
from venues.models import WeddingHall, Bar, Shift, Package
from datetime import date, time
from telegram_bot.models import TelegramBotConfig

User = get_user_model()

class TelegramWebhookTests(APITestCase):
    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(
            phone_number="+998901112233",
            password="testpassword",
            role="VENUE_OWNER",
            first_name="Owner",
            last_name="User"
        )
        self.client_user = User.objects.create_user(
            phone_number="+998904445566",
            password="testpassword",
            role="CLIENT",
            first_name="Client",
            last_name="User"
        )
        self.stranger = User.objects.create_user(
            phone_number="+998907778899",
            password="testpassword",
            role="VENUE_OWNER",
            telegram_chat_id=987654321
        )

        # Create hall and booking dependencies
        self.hall = WeddingHall.objects.create(
            owner=self.owner,
            name="Tashkent Hall",
            address="Tashkent",
            description="Nice hall",
            max_capacity=500
        )
        self.shift = Shift.objects.create(
            hall=self.hall,
            name="Lunch",
            start_time=time(12, 0),
            end_time=time(15, 0)
        )
        self.package = Package.objects.create(
            hall=self.hall,
            guest_count=200,
            price=20000000.00,
            description="Standard"
        )
        # Create hall booking in pending status
        self.hall_booking = HallBooking.objects.create(
            user=self.client_user,
            hall=self.hall,
            shift=self.shift,
            package=self.package,
            date=date(2026, 8, 1),
            total_price=20000000.00,
            deposit_amount=5000000.00,
            status='PENDING'
        )

        # Create bar and booking
        self.bar = Bar.objects.create(
            owner=self.owner,
            name="Tashkent Bar",
            address="Tashkent",
            description="Cozy bar",
            capacity=50,
            price_per_hour=500000.00
        )
        self.bar_booking = BarBooking.objects.create(
            user=self.client_user,
            bar=self.bar,
            date=date(2026, 8, 2),
            start_time=time(18, 0),
            end_time=time(20, 0),
            total_price=1000000.00,
            deposit_amount=200000.00,
            status='PENDING'
        )

        self.webhook_url = reverse('telegram_webhook')

    @patch('telegram_bot.views.send_telegram_message')
    def test_start_command(self, mock_send_message):
        payload = {
            "update_id": 10001,
            "message": {
                "message_id": 1,
                "chat": {"id": 123456789},
                "text": "/start"
            }
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args
        self.assertEqual(args[0], 123456789)
        self.assertIn("telefon raqamingizni yuboring", args[1])
        self.assertIn("keyboard", kwargs["reply_markup"])

    @patch('telegram_bot.views.send_telegram_message')
    def test_contact_sharing_success(self, mock_send_message):
        payload = {
            "update_id": 10002,
            "message": {
                "message_id": 2,
                "chat": {"id": 123456789},
                "contact": {
                    "phone_number": "+998901112233",
                    "first_name": "Owner"
                }
            }
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify telegram_chat_id is updated in the database
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.telegram_chat_id, 123456789)
        
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args
        self.assertEqual(args[0], 123456789)
        self.assertIn("muvaffaqiyatli ulandi", args[1])
        self.assertTrue(kwargs["reply_markup"].get("remove_keyboard"))

    @patch('telegram_bot.views.send_telegram_message')
    def test_contact_sharing_user_not_found(self, mock_send_message):
        payload = {
            "update_id": 10003,
            "message": {
                "message_id": 3,
                "chat": {"id": 123456789},
                "contact": {
                    "phone_number": "+998990000000",
                    "first_name": "Unknown"
                }
            }
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args
        self.assertIn("topilmadi", args[1])

    @patch('telegram_bot.views.answer_callback_query')
    @patch('telegram_bot.views.edit_telegram_message')
    def test_callback_confirm_booking_success(self, mock_edit, mock_answer):
        self.owner.telegram_chat_id = 123456789
        self.owner.save()

        payload = {
            "update_id": 10004,
            "callback_query": {
                "id": "query_123",
                "from": {"id": 123456789},
                "message": {
                    "message_id": 99,
                    "chat": {"id": 123456789},
                    "text": "Yangi Bron So'rovi!\nJoy nomi: Tashkent Hall"
                },
                "data": f"confirm_booking_hall_{self.hall_booking.id}"
            }
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check booking status in db
        self.hall_booking.refresh_from_db()
        self.assertEqual(self.hall_booking.status, 'CONFIRMED')

        mock_answer.assert_called_once()
        args, kwargs = mock_answer.call_args
        self.assertEqual(args[0], "query_123")
        self.assertIn("tasdiqlandi", (args[1] if len(args) > 1 else kwargs.get("text")).lower())
        mock_edit.assert_called_once()

    @patch('telegram_bot.views.answer_callback_query')
    @patch('telegram_bot.views.edit_telegram_message')
    def test_callback_confirm_booking_permission_denied(self, mock_edit, mock_answer):
        payload = {
            "update_id": 10005,
            "callback_query": {
                "id": "query_124",
                "from": {"id": 987654321},  # Stranger's chat_id
                "message": {
                    "message_id": 99,
                    "chat": {"id": 123456789},
                    "text": "Yangi Bron So'rovi!\nJoy nomi: Tashkent Hall"
                },
                "data": f"confirm_booking_hall_{self.hall_booking.id}"
            }
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Status should remain PENDING
        self.hall_booking.refresh_from_db()
        self.assertEqual(self.hall_booking.status, 'PENDING')

        mock_answer.assert_called_once()
        args, kwargs = mock_answer.call_args
        self.assertEqual(args[0], "query_124")
        self.assertIn("ruxsat yo'q", (args[1] if len(args) > 1 else kwargs.get("text")).lower())
        self.assertTrue(kwargs.get("show_alert"))
        mock_edit.assert_not_called()


class TelegramBotConfigTests(APITestCase):
    def setUp(self):
        # Create users with different roles
        self.admin_user = User.objects.create_user(
            phone_number="+998909999999",
            password="testpassword",
            role="ADMIN",
            is_staff=True
        )
        self.client_user = User.objects.create_user(
            phone_number="+998908888888",
            password="testpassword",
            role="CLIENT"
        )
        self.config_url = reverse('admin_telegram_bot_config')

    def test_singleton_behavior(self):
        config1 = TelegramBotConfig.load()
        config2 = TelegramBotConfig.load()
        self.assertEqual(config1.pk, 1)
        self.assertEqual(config2.pk, 1)
        
        # Test creating multiple records forces pk=1
        new_config = TelegramBotConfig(bot_token="test_token")
        new_config.save()
        self.assertEqual(new_config.pk, 1)
        self.assertEqual(TelegramBotConfig.objects.count(), 1)

    def test_get_config_unauthenticated(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_config_client_forbidden(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_config_admin_success(self):
        config = TelegramBotConfig.load()
        config.bot_token = "1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
        config.bot_name = "Custom Bot Name"
        config.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify token is censored
        self.assertEqual(response.data['bot_name'], "Custom Bot Name")
        self.assertEqual(response.data['bot_token'], "123456...wxyZ")

    @patch('telegram_bot.views.configure_telegram_bot')
    def test_patch_config_success(self, mock_configure):
        mock_configure.return_value = True
        
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "bot_token": "9876543210:ZYXwvuTSRqpoNmlKjIhGfEdCBAz",
            "bot_name": "Updated Bot Name",
            "webhook_url": "https://example.com/webhook/"
        }
        response = self.client.patch(self.config_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify db updated
        config = TelegramBotConfig.load()
        self.assertEqual(config.bot_name, "Updated Bot Name")
        self.assertEqual(config.bot_token, "9876543210:ZYXwvuTSRqpoNmlKjIhGfEdCBAz")
        self.assertEqual(config.webhook_url, "https://example.com/webhook/")
        
        mock_configure.assert_called_once()

    @patch('telegram_bot.views.configure_telegram_bot')
    def test_patch_config_preserves_masked_token(self, mock_configure):
        mock_configure.return_value = True
        
        config = TelegramBotConfig.load()
        config.bot_token = "original_token_value_xyz"
        config.save()

        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "bot_token": "origin..._xyz",  # Masked token returned from UI
            "bot_name": "New Name Only"
        }
        response = self.client.patch(self.config_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify bot_token was NOT overwritten by the masked string
        config.refresh_from_db()
        self.assertEqual(config.bot_token, "original_token_value_xyz")
        self.assertEqual(config.bot_name, "New Name Only")
