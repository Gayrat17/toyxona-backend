from datetime import date, time, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from bookings.models import HallBooking, BaseBooking
from users.models import User
from venues.models import Shift, WeddingHall, Package
from .tasks import check_expired_holds


class NotificationTests(TestCase):
    def test_expired_holds_are_cancelled_and_active_hold_is_kept(self):
        user = User.objects.create_user("+998901111111", password="strong-pass-1")
        hall = WeddingHall.objects.create(
            owner=user,
            name="Notification Hall",
            address="Tashkent",
            description="Hall",
            max_capacity=100,
        )
        shift = Shift.objects.create(
            hall=hall, name="Day", start_time=time(10), end_time=time(12)
        )
        package = Package.objects.create(
            hall=hall, guest_count=50, price=100, description="Package"
        )
        expired = HallBooking.objects.create(
            user=user,
            hall=hall,
            shift=shift,
            package=package,
            date=date(2030, 1, 1),
            total_price=100,
            status=BaseBooking.Status.HOLD,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        active = HallBooking.objects.create(
            user=user,
            hall=hall,
            shift=shift,
            package=package,
            date=date(2030, 1, 2),
            total_price=100,
            status=BaseBooking.Status.HOLD,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        result = check_expired_holds()
        expired.refresh_from_db()
        active.refresh_from_db()
        self.assertEqual(result["hall_bookings"], 1)
        self.assertEqual(expired.status, BaseBooking.Status.CANCELLED)
        self.assertEqual(active.status, BaseBooking.Status.HOLD)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="test-secret")
    def test_webhook_rejects_invalid_secret(self):
        response = APIClient().post(
            reverse("notifications-webhook"),
            {"message": {"chat": {"id": 1}, "text": "/start"}},
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong-secret",
        )
        self.assertEqual(response.status_code, 403)
