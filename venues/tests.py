from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from .models import District, Region, Shift, ShiftBlock, WeddingHall


class VenueApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone_number="+998901110001", password="strong-pass-1", role=User.Role.ADMIN
        )
        self.owner = User.objects.create_user(
            phone_number="+998901110002", password="strong-pass-1", role=User.Role.VENUE_OWNER
        )
        self.other_owner = User.objects.create_user(
            phone_number="+998901110003", password="strong-pass-1", role=User.Role.VENUE_OWNER
        )
        self.region = Region.objects.create(name="Toshkent viloyati")
        self.other_region = Region.objects.create(name="Samarqand viloyati")
        self.district = District.objects.create(region=self.region, name="Chilonzor")
        self.hall = WeddingHall.objects.create(
            owner=self.owner,
            region=self.region,
            district=self.district,
            name="Owner Hall",
            address="Chilonzor, Toshkent",
            description="Hall",
            max_capacity=200,
            required_deposit=Decimal("0"),
        )
        self.shift = Shift.objects.create(
            hall=self.hall,
            name="Kechki",
            start_time="18:00",
            end_time="23:00",
        )

    def test_admin_role_can_manage_regions_without_is_staff(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("region-list"), {"name": "Buxoro viloyati"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_cannot_attach_another_owners_hall_to_shift(self):
        self.client.force_authenticate(self.other_owner)
        response = self.client.post(
            reverse("shift-list"),
            {
                "hall": self.hall.pk,
                "name": "Other",
                "start_time": "10:00",
                "end_time": "12:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismatched_region_and_district_are_rejected(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            reverse("hall-detail", args=[self.hall.pk]),
            {"region": self.other_region.pk, "district": self.district.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_create_and_remove_shift_block_for_own_hall(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            reverse("block-list"),
            {
                "hall": self.hall.pk,
                "shift": self.shift.pk,
                "date": "2030-01-01",
                "reason": "Ta'mirlash",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        block = ShiftBlock.objects.get(pk=response.data["id"])
        self.assertEqual(block.hall_id, self.hall.pk)

        response = self.client.delete(reverse("block-detail", args=[block.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
