from datetime import time, timedelta
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from venues.models import Bar, Package, Shift, WeddingHall
from .models import BarBooking, BaseBooking, HallBooking


class BookingApiTests(APITestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            phone_number="+998901112233", password="strong-pass-1", role=User.Role.CLIENT
        )
        self.owner = User.objects.create_user(
            phone_number="+998901112244", password="strong-pass-1", role=User.Role.VENUE_OWNER
        )
        self.other_user = User.objects.create_user(
            phone_number="+998901112255", password="strong-pass-1", role=User.Role.CLIENT
        )
        self.booking_date = timezone.localdate() + timedelta(days=30)
        self.hall = WeddingHall.objects.create(
            owner=self.owner,
            name="Test Hall",
            address="Tashkent",
            description="Test hall",
            max_capacity=300,
            required_deposit=Decimal("0"),
        )
        self.shift = Shift.objects.create(
            hall=self.hall,
            name="Kechki",
            start_time=time(18, 0),
            end_time=time(23, 0),
        )
        self.package = Package.objects.create(
            hall=self.hall,
            guest_count=200,
            price=Decimal("10000000.00"),
            description="Standard",
        )
        self.bar = Bar.objects.create(
            owner=self.owner,
            name="Test Bar",
            address="Tashkent",
            description="Test bar",
            capacity=50,
            price_per_hour=Decimal("100000.00"),
            required_deposit=Decimal("0"),
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_hall_booking_price_and_double_booking_protection(self):
        self.authenticate(self.client_user)
        payload = {
            "hall": self.hall.pk,
            "shift": self.shift.pk,
            "package": self.package.pk,
            "date": self.booking_date.isoformat(),
            "deposit_amount": "0",
        }
        response = self.client.post(reverse("hall-booking-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_price"], "10000000.00")

        conflict = self.client.post(reverse("hall-booking-list"), payload, format="json")
        self.assertEqual(conflict.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("faol band", str(conflict.data))

    def test_bar_booking_is_prorated_and_overlaps_are_rejected(self):
        self.authenticate(self.client_user)
        payload = {
            "bar": self.bar.pk,
            "date": self.booking_date.isoformat(),
            "start_time": "18:00",
            "end_time": "19:30",
            "guest_count": 10,
            "deposit_amount": "0",
        }
        response = self.client.post(reverse("bar-booking-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_price"], "150000.00")

        conflict = self.client.post(
            reverse("bar-booking-list"),
            {**payload, "start_time": "19:00", "end_time": "20:00"},
            format="json",
        )
        self.assertEqual(conflict.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_cannot_confirm_or_change_booking_fields(self):
        booking = HallBooking.objects.create(
            user=self.client_user,
            hall=self.hall,
            shift=self.shift,
            package=self.package,
            date=self.booking_date,
            total_price=self.package.price,
        )
        self.authenticate(self.client_user)
        response = self.client.patch(
            reverse("hall-booking-detail", args=[booking.pk]),
            {"status": BaseBooking.Status.CONFIRMED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BaseBooking.Status.PENDING)

        other_response = self.client.patch(
            reverse("hall-booking-detail", args=[booking.pk]),
            {"date": (self.booking_date + timedelta(days=1)).isoformat()},
            format="json",
        )
        self.assertEqual(other_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_confirm_and_client_can_cancel(self):
        booking = HallBooking.objects.create(
            user=self.client_user,
            hall=self.hall,
            shift=self.shift,
            package=self.package,
            date=self.booking_date,
            total_price=self.package.price,
        )
        self.authenticate(self.owner)
        response = self.client.patch(
            reverse("hall-booking-detail", args=[booking.pk]),
            {"status": BaseBooking.Status.CONFIRMED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BaseBooking.Status.CONFIRMED)

        dedicated = self.client.patch(
            reverse("hall-booking-status", args=[booking.pk]),
            {"status": BaseBooking.Status.REJECTED},
            format="json",
        )
        self.assertEqual(dedicated.status_code, status.HTTP_400_BAD_REQUEST)

        self.authenticate(self.client_user)
        response = self.client.delete(reverse("hall-booking-detail", args=[booking.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BaseBooking.Status.CANCELLED)

    def test_hold_gets_expiration_and_calendar_hides_cancelled_booking(self):
        self.authenticate(self.owner)
        response = self.client.post(
            reverse("hall-booking-list"),
            {
                "hall": self.hall.pk,
                "shift": self.shift.pk,
                "package": self.package.pk,
                "date": self.booking_date.isoformat(),
                "status": BaseBooking.Status.HOLD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = HallBooking.objects.get(pk=response.data["id"])
        self.assertIsNotNone(booking.expires_at)
        self.assertGreater(booking.expires_at, timezone.now())

        booking.status = BaseBooking.Status.CANCELLED
        booking.expires_at = None
        booking.save(update_fields=["status", "expires_at"])
        calendar = self.client.get(
            reverse("hall-calendar", args=[self.hall.pk]),
            {"year": self.booking_date.year, "month": self.booking_date.month},
        )
        self.assertEqual(calendar.status_code, status.HTTP_200_OK)
        self.assertEqual(calendar.data["busy_shifts"], [])

    def test_anonymous_cannot_access_bookings(self):
        response = self.client.get(reverse("hall-booking-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
