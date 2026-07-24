from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from decimal import Decimal
from venues.models import ShiftBlock
from .models import HallBooking, BarBooking

class HallBookingSerializer(serializers.ModelSerializer):
    """
    Serializer for HallBooking, implementing double-booking checks,
    ShiftBlock checks, and automated pricing.
    """
    remaining_amount = serializers.ReadOnlyField()
    user_phone = serializers.ReadOnlyField(source='user.phone_number')

    class Meta:
        model = HallBooking
        fields = (
            'id', 'user', 'user_phone', 'hall', 'shift', 'package', 'decoration',
            'date', 'total_price', 'deposit_amount', 'is_deposit_paid',
            'status', 'expires_at', 'meeting_date', 'admin_notes', 'created_at',
            'remaining_amount'
        )
        read_only_fields = ('user', 'total_price', 'expires_at', 'created_at')

    def validate(self, attrs):
        # Resolve values from input or existing instance (for partial updates)
        hall = attrs.get('hall') or (self.instance.hall if self.instance else None)
        shift = attrs.get('shift') or (self.instance.shift if self.instance else None)
        package = attrs.get('package') or (self.instance.package if self.instance else None)
        decoration = attrs.get('decoration') or (self.instance.decoration if self.instance else None)
        date = attrs.get('date') or (self.instance.date if self.instance else None)

        if not hall or not shift or not date:
            raise serializers.ValidationError("Zal, smena va sana kiritilishi shart.")

        # Ensure all elements belong to the correct WeddingHall
        if shift.hall != hall:
            raise serializers.ValidationError({"shift": "Tanlangan smena ushbu to'yxonaga tegishli emas."})
        if package and package.hall != hall:
            raise serializers.ValidationError({"package": "Tanlangan paket ushbu to'yxonaga tegishli emas."})
        if decoration and decoration.hall != hall:
            raise serializers.ValidationError({"decoration": "Tanlangan dekoratsiya ushbu to'yxonaga tegishli emas."})

        # Double-booking protection: checks for CONFIRMED, PENDING, or active HOLDs on same date/shift
        now = timezone.now()
        conflicts = HallBooking.objects.filter(
            hall=hall,
            date=date,
            shift=shift
        ).filter(
            Q(status__in=['PENDING', 'CONFIRMED']) |
            Q(status='HOLD', expires_at__gt=now) |
            Q(status='HOLD', expires_at__isnull=True)
        )

        if self.instance:
            conflicts = conflicts.exclude(id=self.instance.id)

        if conflicts.exists():
            raise serializers.ValidationError("Ushbu sana va smenada faol band qilingan bron mavjud.")

        # ShiftBlock validation: ensure that the date and shift is not blocked by admin
        if ShiftBlock.objects.filter(hall=hall, shift=shift, date=date).exists():
            raise serializers.ValidationError("Ushbu sana va smena admin tomonidan yopib qo'yilgan (bloklangan).")

        return attrs

    def create(self, validated_data):
        package = validated_data['package']
        decoration = validated_data.get('decoration')

        # Automated Pricing Calculation
        price = package.price
        if decoration:
            price += decoration.additional_price
        validated_data['total_price'] = price

        # Handle expiration for offline HOLD status
        status = validated_data.get('status', 'PENDING')
        if status == 'HOLD':
            validated_data['expires_at'] = timezone.now() + timedelta(hours=24)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        package = validated_data.get('package', instance.package)
        decoration = validated_data.get('decoration', instance.decoration)

        # Recalculate price if package or decoration changed
        price = package.price
        if decoration:
            price += decoration.additional_price
        validated_data['total_price'] = price

        # Set or clean expires_at based on status changes
        status = validated_data.get('status', instance.status)
        if status == 'HOLD' and not instance.expires_at:
            validated_data['expires_at'] = timezone.now() + timedelta(hours=24)
        elif status != 'HOLD':
            validated_data['expires_at'] = None

        return super().update(instance, validated_data)


class BarBookingSerializer(serializers.ModelSerializer):
    """
    Serializer for BarBooking, implementing time overlap validation,
    and automated hourly slot pricing.
    """
    remaining_amount = serializers.ReadOnlyField()
    user_phone = serializers.ReadOnlyField(source='user.phone_number')

    class Meta:
        model = BarBooking
        fields = (
            'id', 'user', 'user_phone', 'bar', 'start_time', 'end_time', 'guest_count',
            'date', 'total_price', 'deposit_amount', 'is_deposit_paid',
            'status', 'expires_at', 'meeting_date', 'admin_notes', 'created_at',
            'remaining_amount'
        )
        read_only_fields = ('user', 'total_price', 'expires_at', 'created_at')

    def validate(self, attrs):
        bar = attrs.get('bar') or (self.instance.bar if self.instance else None)
        date = attrs.get('date') or (self.instance.date if self.instance else None)
        start_time = attrs.get('start_time') or (self.instance.start_time if self.instance else None)
        end_time = attrs.get('end_time') or (self.instance.end_time if self.instance else None)

        if not bar or not date or not start_time or not end_time:
            raise serializers.ValidationError("Bar, sana, kirish va chiqish vaqtlari kiritilishi shart.")

        # Ensure start_time is before end_time
        if start_time >= end_time:
            raise serializers.ValidationError({"end_time": "Chiqish vaqti kirish vaqtidan keyin bo'lishi shart."})

        # Time overlap validation
        now = timezone.now()
        conflicts = BarBooking.objects.filter(
            bar=bar,
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).filter(
            Q(status__in=['PENDING', 'CONFIRMED']) |
            Q(status='HOLD', expires_at__gt=now) |
            Q(status='HOLD', expires_at__isnull=True)
        )

        if self.instance:
            conflicts = conflicts.exclude(id=self.instance.id)

        if conflicts.exists():
            raise serializers.ValidationError("Ushbu vaqt oralig'i boshqa bron bilan kesishmoqda.")

        return attrs

    def create(self, validated_data):
        bar = validated_data['bar']
        date = validated_data['date']
        start_time = validated_data['start_time']
        end_time = validated_data['end_time']

        # Calculate duration in hours
        start_dt = datetime.combine(date, start_time)
        end_dt = datetime.combine(date, end_time)
        duration_seconds = (end_dt - start_dt).total_seconds()
        duration_hours = Decimal(str(duration_seconds / 3600.0))

        # Auto Calculate Price
        validated_data['total_price'] = duration_hours * bar.price_per_hour

        # Handle expiration for offline HOLD status
        status = validated_data.get('status', 'PENDING')
        if status == 'HOLD':
            validated_data['expires_at'] = timezone.now() + timedelta(hours=24)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        bar = validated_data.get('bar', instance.bar)
        date = validated_data.get('date', instance.date)
        start_time = validated_data.get('start_time', instance.start_time)
        end_time = validated_data.get('end_time', instance.end_time)

        # Recalculate price
        start_dt = datetime.combine(date, start_time)
        end_dt = datetime.combine(date, end_time)
        duration_seconds = (end_dt - start_dt).total_seconds()
        duration_hours = Decimal(str(duration_seconds / 3600.0))
        validated_data['total_price'] = duration_hours * bar.price_per_hour

        # Set or clean expires_at based on status changes
        status = validated_data.get('status', instance.status)
        if status == 'HOLD' and not instance.expires_at:
            validated_data['expires_at'] = timezone.now() + timedelta(hours=24)
        elif status != 'HOLD':
            validated_data['expires_at'] = None

        return super().update(instance, validated_data)
