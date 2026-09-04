from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.fields import ReadOnlyField
from rest_framework.serializers import ModelSerializer

from users.models import User
from venues.models import Bar, Package, WeddingHall
from .models import BarBooking, BaseBooking, HallBooking
from .services import (
    ACTIVE_BOOKING_STATUSES,
    assert_bar_available,
    assert_hall_available,
    get_active_booking_q_filter,
    validate_status_transition,
)

HOLD_EXPIRATION_HOURS = 24
MONEY_QUANTUM = Decimal("0.01")


def _value(attrs: Dict[str, Any], field_name: str, instance: Optional[Any] = None) -> Any:
    """Get an explicitly supplied value, preserving explicit ``None`` on PATCH."""

    if field_name in attrs:
        return attrs[field_name]
    return getattr(instance, field_name, None) if instance is not None else None


def _is_privileged(user: Any) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "role", None)
            in (User.Role.ADMIN, User.Role.VENUE_OWNER)
        )
    )


def _calculate_bar_price(bar: Bar, booking_date, start_time, end_time) -> Decimal:
    duration_seconds = Decimal(
        (
            datetime.combine(booking_date, end_time)
            - datetime.combine(booking_date, start_time)
        ).total_seconds()
    )
    hours = duration_seconds / Decimal("3600")
    return (hours * bar.price_per_hour).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class BaseBookingSerializer(ModelSerializer):
    """Shared access and payment validation for both booking types."""

    remaining_amount = ReadOnlyField()
    user_phone = ReadOnlyField(source="user.phone_number")

    def _request_user(self) -> Any:
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _validate_access(self, attrs: Dict[str, Any]) -> None:
        user = self._request_user()
        if not user or not getattr(user, "is_authenticated", False):
            # Direct serializer usage (for example a management command) can
            # still validate a booking; API permissions protect HTTP requests.
            return

        requested_status = _value(attrs, "status", self.instance) or BaseBooking.Status.PENDING
        if self.instance is not None:
            if not _is_privileged(user):
                changed_fields = set(attrs) - {"status"}
                if changed_fields or requested_status != BaseBooking.Status.CANCELLED:
                    raise serializers.ValidationError(
                        "Mijoz faqat o'z bronini bekor qilishi mumkin."
                    )
            validate_status_transition(self.instance.status, requested_status)
            if (
                self.instance.status == BaseBooking.Status.HOLD
                and self.instance.expires_at is not None
                and self.instance.expires_at <= timezone.now()
                and requested_status == BaseBooking.Status.CONFIRMED
            ):
                raise serializers.ValidationError(
                    {"status": "HOLD muddati tugagan, bronni tasdiqlab bo'lmaydi."}
                )
        elif not _is_privileged(user) and requested_status != BaseBooking.Status.PENDING:
            raise serializers.ValidationError(
                {"status": "Mijoz yangi bronni faqat PENDING holatida yuborishi mumkin."}
            )

    def _validate_deposit(
        self, attrs: Dict[str, Any], total_price: Decimal, venue_required_deposit: Decimal
    ) -> None:
        deposit = _value(attrs, "deposit_amount", self.instance)
        if deposit is None:
            deposit = Decimal("0")
        if deposit < 0:
            raise serializers.ValidationError({"deposit_amount": "Zakalat manfiy bo'lishi mumkin emas."})
        if deposit > total_price:
            raise serializers.ValidationError(
                {"deposit_amount": "Zakalat umumiy summadan oshmasligi kerak."}
            )
        # Zero is valid for an initial request; once a deposit is supplied it
        # may not be below the venue's configured minimum.
        if deposit and venue_required_deposit and deposit < venue_required_deposit:
            raise serializers.ValidationError(
                {"deposit_amount": "Zakalat miqdori joyning minimal zakalatidan kam."}
            )

    def _validate_owner_target(self, venue: Any) -> None:
        user = self._request_user()
        if not user or not getattr(user, "is_authenticated", False) or not _is_privileged(user):
            return
        if user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
            return
        if venue.owner_id != user.id:
            raise serializers.ValidationError(
                "Joy egasi faqat o'z joyidagi bronni boshqarishi mumkin."
            )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_access(attrs)
        return attrs


class HallBookingSerializer(BaseBookingSerializer):
    """Validate, price, and persist a wedding-hall booking atomically."""

    class Meta:
        model = HallBooking
        fields = (
            "id", "user", "user_phone", "hall", "shift", "package", "decoration",
            "date", "total_price", "deposit_amount", "is_deposit_paid", "status",
            "expires_at", "meeting_date", "admin_notes", "created_at", "remaining_amount",
        )
        read_only_fields = (
            "user", "total_price", "expires_at", "created_at", "remaining_amount", "user_phone"
        )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        super().validate(attrs)
        hall = _value(attrs, "hall", self.instance)
        shift = _value(attrs, "shift", self.instance)
        package = _value(attrs, "package", self.instance)
        decoration = _value(attrs, "decoration", self.instance)
        booking_date = _value(attrs, "date", self.instance)
        requested_status = _value(attrs, "status", self.instance) or BaseBooking.Status.PENDING

        if not hall or not shift or not package or not booking_date:
            raise serializers.ValidationError("Zal, smena, paket va sana kiritilishi shart.")
        if booking_date < timezone.localdate() and requested_status not in (
            BaseBooking.Status.CANCELLED,
            BaseBooking.Status.REJECTED,
        ):
            raise serializers.ValidationError({"date": "O'tgan sanaga bron qilib bo'lmaydi."})
        if shift.hall_id != hall.id:
            raise serializers.ValidationError({"shift": "Tanlangan smena ushbu zalga tegishli emas."})
        if not shift.is_active and requested_status not in (
            BaseBooking.Status.CANCELLED, BaseBooking.Status.REJECTED
        ):
            raise serializers.ValidationError({"shift": "Tanlangan smena hozir faol emas."})
        if package.hall_id != hall.id:
            raise serializers.ValidationError({"package": "Tanlangan paket ushbu zalga tegishli emas."})
        if package.guest_count > hall.max_capacity:
            raise serializers.ValidationError(
                {"package": "Paketdagi mehmonlar soni zal sig'imidan oshib ketgan."}
            )
        if decoration is not None and decoration.hall_id != hall.id:
            raise serializers.ValidationError(
                {"decoration": "Tanlangan dekoratsiya ushbu zalga tegishli emas."}
            )

        total_price = package.price + (decoration.additional_price if decoration else Decimal("0"))
        self._validate_deposit(attrs, total_price, hall.required_deposit)
        self._validate_owner_target(hall)
        if requested_status in ACTIVE_BOOKING_STATUSES or requested_status == BaseBooking.Status.HOLD:
            assert_hall_available(
                hall_id=hall.id,
                shift_id=shift.id,
                booking_date=booking_date,
                exclude_id=self.instance.pk if self.instance else None,
            )
        return attrs

    def _set_expiration(self, booking: HallBooking, requested_status: str) -> None:
        now = timezone.now()
        if requested_status == BaseBooking.Status.HOLD:
            if (
                booking.status != BaseBooking.Status.HOLD
                or not booking.expires_at
                or booking.expires_at <= now
            ):
                booking.expires_at = now + timedelta(hours=HOLD_EXPIRATION_HOURS)
        else:
            booking.expires_at = None

    def create(self, validated_data: Dict[str, Any]) -> HallBooking:
        hall = validated_data["hall"]
        package = validated_data["package"]
        decoration = validated_data.get("decoration")
        requested_status = validated_data.get("status", BaseBooking.Status.PENDING)
        validated_data["total_price"] = package.price + (
            decoration.additional_price if decoration else Decimal("0")
        )
        if requested_status == BaseBooking.Status.HOLD:
            validated_data["expires_at"] = timezone.now() + timedelta(hours=HOLD_EXPIRATION_HOURS)

        with transaction.atomic():
            locked_hall = WeddingHall.objects.select_for_update().get(pk=hall.pk)
            if requested_status in ACTIVE_BOOKING_STATUSES or requested_status == BaseBooking.Status.HOLD:
                assert_hall_available(
                    hall_id=locked_hall.pk,
                    shift_id=validated_data["shift"].pk,
                    booking_date=validated_data["date"],
                )
            validated_data["hall"] = locked_hall
            booking = HallBooking.objects.create(**validated_data)
        return booking

    def update(self, instance: HallBooking, validated_data: Dict[str, Any]) -> HallBooking:
        with transaction.atomic():
            target_hall_id = validated_data.get("hall", instance.hall).pk
            locked_hall = WeddingHall.objects.select_for_update().get(pk=target_hall_id)
            current = HallBooking.objects.select_for_update().get(pk=instance.pk)
            shift = validated_data.get("shift", current.shift)
            package = validated_data.get("package", current.package)
            decoration = validated_data["decoration"] if "decoration" in validated_data else current.decoration
            booking_date = validated_data.get("date", current.date)
            requested_status = validated_data.get("status", current.status)

            validate_status_transition(current.status, requested_status)
            if requested_status in ACTIVE_BOOKING_STATUSES or requested_status == BaseBooking.Status.HOLD:
                assert_hall_available(
                    hall_id=locked_hall.pk,
                    shift_id=shift.pk,
                    booking_date=booking_date,
                    exclude_id=current.pk,
                )
            validated_data["hall"] = locked_hall
            validated_data["total_price"] = package.price + (
                decoration.additional_price if decoration else Decimal("0")
            )
            for field, value in validated_data.items():
                setattr(current, field, value)
            self._set_expiration(current, requested_status)
            current.save()
            return current


class BarBookingSerializer(BaseBookingSerializer):
    """Validate, price, and persist an hourly bar booking atomically."""

    class Meta:
        model = BarBooking
        fields = (
            "id", "user", "user_phone", "bar", "start_time", "end_time", "guest_count",
            "date", "total_price", "deposit_amount", "is_deposit_paid", "status",
            "expires_at", "meeting_date", "admin_notes", "created_at", "remaining_amount",
        )
        read_only_fields = (
            "user", "total_price", "expires_at", "created_at", "remaining_amount", "user_phone"
        )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        super().validate(attrs)
        bar = _value(attrs, "bar", self.instance)
        booking_date = _value(attrs, "date", self.instance)
        start_time = _value(attrs, "start_time", self.instance)
        end_time = _value(attrs, "end_time", self.instance)
        guest_count = _value(attrs, "guest_count", self.instance)
        requested_status = _value(attrs, "status", self.instance) or BaseBooking.Status.PENDING

        if not bar or not booking_date or not start_time or not end_time:
            raise serializers.ValidationError("Bar, sana, kirish va chiqish vaqtlari kiritilishi shart.")
        if booking_date < timezone.localdate() and requested_status not in (
            BaseBooking.Status.CANCELLED,
            BaseBooking.Status.REJECTED,
        ):
            raise serializers.ValidationError({"date": "O'tgan sanaga bron qilib bo'lmaydi."})
        if start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "Chiqish vaqti kirish vaqtidan keyin bo'lishi shart."}
            )
        if guest_count is not None and guest_count > bar.capacity:
            raise serializers.ValidationError(
                {"guest_count": "Mehmonlar soni bar sig'imidan oshmasligi kerak."}
            )

        total_price = _calculate_bar_price(bar, booking_date, start_time, end_time)
        self._validate_deposit(attrs, total_price, bar.required_deposit)
        self._validate_owner_target(bar)
        if requested_status in ACTIVE_BOOKING_STATUSES or requested_status == BaseBooking.Status.HOLD:
            assert_bar_available(
                bar_id=bar.id,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                exclude_id=self.instance.pk if self.instance else None,
            )
        return attrs

    def _set_expiration(self, booking: BarBooking, requested_status: str) -> None:
        now = timezone.now()
        if requested_status == BaseBooking.Status.HOLD:
            if (
                booking.status != BaseBooking.Status.HOLD
                or not booking.expires_at
                or booking.expires_at <= now
            ):
                booking.expires_at = now + timedelta(hours=HOLD_EXPIRATION_HOURS)
        else:
            booking.expires_at = None

    def create(self, validated_data: Dict[str, Any]) -> BarBooking:
        bar = validated_data["bar"]
        requested_status = validated_data.get("status", BaseBooking.Status.PENDING)
        validated_data["total_price"] = _calculate_bar_price(
            bar, validated_data["date"], validated_data["start_time"], validated_data["end_time"]
        )
        if requested_status == BaseBooking.Status.HOLD:
            validated_data["expires_at"] = timezone.now() + timedelta(hours=HOLD_EXPIRATION_HOURS)

        with transaction.atomic():
            locked_bar = Bar.objects.select_for_update().get(pk=bar.pk)
            if requested_status in ACTIVE_BOOKING_STATUSES or requested_status == BaseBooking.Status.HOLD:
                assert_bar_available(
                    bar_id=locked_bar.pk,
                    booking_date=validated_data["date"],
                    start_time=validated_data["start_time"],
                    end_time=validated_data["end_time"],
                )
            validated_data["bar"] = locked_bar
            booking = BarBooking.objects.create(**validated_data)
        return booking

    def update(self, instance: BarBooking, validated_data: Dict[str, Any]) -> BarBooking:
        with transaction.atomic():
            target_bar_id = validated_data.get("bar", instance.bar).pk
            locked_bar = Bar.objects.select_for_update().get(pk=target_bar_id)
            current = BarBooking.objects.select_for_update().get(pk=instance.pk)
            booking_date = validated_data.get("date", current.date)
            start_time = validated_data.get("start_time", current.start_time)
            end_time = validated_data.get("end_time", current.end_time)
            requested_status = validated_data.get("status", current.status)

            validate_status_transition(current.status, requested_status)
            if requested_status in ACTIVE_BOOKING_STATUSES or requested_status == BaseBooking.Status.HOLD:
                assert_bar_available(
                    bar_id=locked_bar.pk,
                    booking_date=booking_date,
                    start_time=start_time,
                    end_time=end_time,
                    exclude_id=current.pk,
                )
            validated_data["bar"] = locked_bar
            validated_data["total_price"] = _calculate_bar_price(
                locked_bar, booking_date, start_time, end_time
            )
            for field, value in validated_data.items():
                setattr(current, field, value)
            self._set_expiration(current, requested_status)
            current.save()
            return current


class BookingStatusSerializer(serializers.Serializer):
    """Payload for the dedicated venue-owner status endpoint."""

    status = serializers.ChoiceField(choices=BaseBooking.Status.choices)
