import json
import logging
from typing import Any, Dict, Optional
from rest_framework import serializers
from django.contrib.auth import get_user_model
from users.models import User as CustomUser
from .models import Region, District, WeddingHall, Bar, Media, Shift, Package, Decoration, ShiftBlock

logger = logging.getLogger(__name__)
User = get_user_model()


class DistrictSerializer(serializers.ModelSerializer):
    """
    Serializer for District (Tuman).
    """
    class Meta:
        model = District
        fields = ('id', 'region', 'name', 'order')


class RegionSerializer(serializers.ModelSerializer):
    """
    Serializer for Region (Viloyat), including nested districts.
    """
    districts = DistrictSerializer(many=True, read_only=True)

    class Meta:
        model = Region
        fields = ('id', 'name', 'order', 'districts')


class MediaSerializer(serializers.ModelSerializer):
    """
    Serializer for Media / VenueImage. Returns absolute file and image URL for frontend.
    """
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = ('id', 'image', 'file', 'image_url', 'type', 'is_main', 'position', 'created_at')
        read_only_fields = ('created_at',)

    def get_image_url(self, obj: Media) -> Optional[str]:
        request = self.context.get('request')
        target = obj.image or obj.file
        if target and hasattr(target, 'url'):
            if request is not None:
                return request.build_absolute_uri(target.url)
            return target.url
        return None


VenueImageSerializer = MediaSerializer


class BaseVenueSerializer(serializers.ModelSerializer):
    """
    Base serializer providing shared logic for WeddingHall and Bar models:
    - Cover image URL resolution
    - JSON amenities parsing
    - Cover image file upload/deletion
    - Gallery media upload/deletion
    """
    owner_phone = serializers.ReadOnlyField(source='owner.phone_number')
    region_name = serializers.ReadOnlyField(source='region.name')
    district_name = serializers.ReadOnlyField(source='district.name')
    cover_image_url = serializers.SerializerMethodField()
    gallery_images = MediaSerializer(many=True, read_only=True)

    venue_fk_field: str = 'hall'  # Subclasses specify 'hall' or 'bar'

    def get_cover_image_url(self, obj: Any) -> Optional[str]:
        request = self.context.get('request')
        if obj.cover_image and hasattr(obj.cover_image, 'url'):
            if request is not None:
                return request.build_absolute_uri(obj.cover_image.url)
            return obj.cover_image.url
        return None

    def to_internal_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if 'amenities' in data and isinstance(data['amenities'], str):
            try:
                mutable_data = data.copy()
                mutable_data['amenities'] = json.loads(data['amenities'])
                return super().to_internal_value(mutable_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON string passed for amenities: {e}")
        return super().to_internal_value(data)

    def _process_gallery_uploads(self, instance: Any, request: Any) -> None:
        """Helper method to process uploaded gallery files."""
        if not request or not hasattr(request, 'FILES'):
            return
        gallery_files = request.FILES.getlist('gallery_images') or request.FILES.getlist('gallery_images[]')
        for file in gallery_files:
            Media.objects.create(**{self.venue_fk_field: instance, 'image': file})

    def create(self, validated_data: Dict[str, Any]) -> Any:
        request = self.context.get('request')
        if request and 'cover_image' in request.FILES and 'cover_image' not in validated_data:
            validated_data['cover_image'] = request.FILES['cover_image']

        instance = super().create(validated_data)
        self._process_gallery_uploads(instance, request)
        return instance

    def update(self, instance: Any, validated_data: Dict[str, Any]) -> Any:
        request = self.context.get('request')

        # 1. Delete cover image if requested
        if request and request.data.get('delete_cover_image') in ['true', 'True', True]:
            if instance.cover_image:
                instance.cover_image.delete(save=False)
                instance.cover_image = None

        # 2. Update cover image if new file sent
        if request and 'cover_image' in request.FILES:
            instance.cover_image = request.FILES['cover_image']

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 3. Delete specific gallery images by ID
        if request and 'deleted_gallery_ids' in request.data:
            try:
                raw_ids = request.data.get('deleted_gallery_ids')
                deleted_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
                if isinstance(deleted_ids, list) and deleted_ids:
                    Media.objects.filter(id__in=deleted_ids, **{self.venue_fk_field: instance}).delete()
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Error parsing deleted_gallery_ids: {e}")

        # 4. Add new gallery images
        self._process_gallery_uploads(instance, request)

        return instance


class WeddingHallSerializer(BaseVenueSerializer):
    """
    Serializer for WeddingHall including region, district, cover image, video link, map link, amenities, and gallery media.
    """
    venue_fk_field = 'hall'

    class Meta:
        model = WeddingHall
        fields = (
            'id', 'owner', 'owner_phone', 'region', 'region_name', 'district', 'district_name',
            'name', 'address', 'description', 'max_capacity', 'required_deposit', 
            'cover_image', 'cover_image_url', 'video_url', 'map_link', 'amenities', 
            'gallery_images', 'created_at'
        )
        read_only_fields = ('owner', 'created_at')


class BarSerializer(BaseVenueSerializer):
    """
    Serializer for Bar including region, district, cover image, video link, map link, amenities, and gallery media.
    """
    venue_fk_field = 'bar'

    class Meta:
        model = Bar
        fields = (
            'id', 'owner', 'owner_phone', 'region', 'region_name', 'district', 'district_name',
            'name', 'address', 'description', 'capacity', 'price_per_hour', 
            'required_deposit', 'cover_image', 'cover_image_url', 'video_url', 
            'map_link', 'amenities', 'gallery_images', 'created_at'
        )
        read_only_fields = ('owner', 'created_at')


def _validate_hall_ownership(serializer: serializers.ModelSerializer, value: WeddingHall) -> WeddingHall:
    """Helper method to validate user ownership over a WeddingHall resource."""
    request = serializer.context.get('request')
    if request and request.user:
        if request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN:
            return value
        if value.owner != request.user:
            raise serializers.ValidationError("Siz faqat o'zingizga tegishli restoran uchun ruxsat berilgan resurslarni o'zgartirishingiz mumkin.")
    return value


class ShiftSerializer(serializers.ModelSerializer):
    """
    Serializer for Shifts. Validates ownership of the referenced WeddingHall.
    """
    class Meta:
        model = Shift
        fields = ('id', 'hall', 'name', 'start_time', 'end_time', 'is_active')

    def validate_hall(self, value: WeddingHall) -> WeddingHall:
        return _validate_hall_ownership(self, value)


class PackageSerializer(serializers.ModelSerializer):
    """
    Serializer for Packages. Validates ownership of the referenced WeddingHall.
    """
    class Meta:
        model = Package
        fields = ('id', 'hall', 'guest_count', 'price', 'description')

    def validate_hall(self, value: WeddingHall) -> WeddingHall:
        return _validate_hall_ownership(self, value)


class DecorationSerializer(serializers.ModelSerializer):
    """
    Serializer for Decorations. Validates ownership of the referenced WeddingHall.
    """
    class Meta:
        model = Decoration
        fields = ('id', 'hall', 'name', 'additional_price')

    def validate_hall(self, value: WeddingHall) -> WeddingHall:
        return _validate_hall_ownership(self, value)


class ShiftBlockSerializer(serializers.ModelSerializer):
    """
    Serializer for ShiftBlocks. Validates ownership and ensures the shift belongs to the hall.
    """
    class Meta:
        model = ShiftBlock
        fields = ('id', 'hall', 'shift', 'date', 'reason')

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        hall = attrs.get('hall')
        shift = attrs.get('shift')
        request = self.context.get('request')

        if request and request.user:
            if not (request.user.is_superuser or getattr(request.user, 'role', None) == CustomUser.Role.ADMIN):
                if hall and hall.owner != request.user:
                    raise serializers.ValidationError({"hall": "Siz faqat o'zingizga tegishli restoranni bloklay olasiz."})

        if shift and hall and shift.hall != hall:
            raise serializers.ValidationError({"shift": "Tanlangan smena ushbu restoranga tegishli emas."})

        return attrs
