from rest_framework import serializers
from .models import WeddingHall, Bar, Shift, Package, Decoration, ShiftBlock

class WeddingHallSerializer(serializers.ModelSerializer):
    """
    Serializer for WeddingHall. The owner field is read-only and set automatically.
    """
    owner_phone = serializers.ReadOnlyField(source='owner.phone_number')

    class Meta:
        model = WeddingHall
        fields = ('id', 'owner', 'owner_phone', 'name', 'address', 'description', 'max_capacity', 'required_deposit', 'created_at')
        read_only_fields = ('owner', 'created_at')

class BarSerializer(serializers.ModelSerializer):
    """
    Serializer for Bar. The owner field is read-only and set automatically.
    """
    owner_phone = serializers.ReadOnlyField(source='owner.phone_number')

    class Meta:
        model = Bar
        fields = ('id', 'owner', 'owner_phone', 'name', 'address', 'description', 'capacity', 'price_per_hour', 'required_deposit', 'created_at')
        read_only_fields = ('owner', 'created_at')

class ShiftSerializer(serializers.ModelSerializer):
    """
    Serializer for Shifts. Validates ownership of the referenced WeddingHall.
    """
    class Meta:
        model = Shift
        fields = ('id', 'hall', 'name', 'start_time', 'end_time', 'is_active')

    def validate_hall(self, value):
        request = self.context.get('request')
        if request and request.user:
            # Admins or superusers can bypass ownership check
            if request.user.is_superuser or request.user.role == 'ADMIN':
                return value
            if value.owner != request.user:
                raise serializers.ValidationError("Siz faqat o'zingizga tegishli to'yxona uchun smena qo'shishingiz/tahrirlashingiz mumkin.")
        return value

class PackageSerializer(serializers.ModelSerializer):
    """
    Serializer for Packages. Validates ownership of the referenced WeddingHall.
    """
    class Meta:
        model = Package
        fields = ('id', 'hall', 'guest_count', 'price', 'description')

    def validate_hall(self, value):
        request = self.context.get('request')
        if request and request.user:
            if request.user.is_superuser or request.user.role == 'ADMIN':
                return value
            if value.owner != request.user:
                raise serializers.ValidationError("Siz faqat o'zingizga tegishli to'yxona uchun paket qo'shishingiz/tahrirlashingiz mumkin.")
        return value

class DecorationSerializer(serializers.ModelSerializer):
    """
    Serializer for Decorations. Validates ownership of the referenced WeddingHall.
    """
    class Meta:
        model = Decoration
        fields = ('id', 'hall', 'name', 'additional_price')

    def validate_hall(self, value):
        request = self.context.get('request')
        if request and request.user:
            if request.user.is_superuser or request.user.role == 'ADMIN':
                return value
            if value.owner != request.user:
                raise serializers.ValidationError("Siz faqat o'zingizga tegishli to'yxona uchun dekoratsiya qo'shishingiz/tahrirlashingiz mumkin.")
        return value

class ShiftBlockSerializer(serializers.ModelSerializer):
    """
    Serializer for ShiftBlocks. Validates ownership and ensures the shift belongs to the hall.
    """
    class Meta:
        model = ShiftBlock
        fields = ('id', 'hall', 'shift', 'date', 'reason')

    def validate(self, attrs):
        hall = attrs.get('hall')
        shift = attrs.get('shift')
        request = self.context.get('request')

        # Check ownership
        if request and request.user:
            if not (request.user.is_superuser or request.user.role == 'ADMIN'):
                if hall and hall.owner != request.user:
                    raise serializers.ValidationError({"hall": "Siz faqat o'zingizga tegishli to'yxonani bloklay olasiz."})

        # Check shift matches hall
        if shift and hall and shift.hall != hall:
            raise serializers.ValidationError({"shift": "Tanlangan smena ushbu to'yxonaga tegishli emas."})

        return attrs
