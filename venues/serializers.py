from __future__ import annotations

import json
from typing import Any, Dict, Optional

from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField, ReadOnlyField
from rest_framework.serializers import ModelSerializer

from users.models import User as CustomUser
from .models import (
    Bar,
    Decoration,
    District,
    Media,
    Package,
    Region,
    Shift,
    ShiftBlock,
    WeddingHall,
)

class DistrictSerializer(ModelSerializer):
    class Meta:
        model = District
        fields = ("id", "region", "name", "order")


class RegionSerializer(ModelSerializer):
    districts = DistrictSerializer(many=True, read_only=True)

    class Meta:
        model = Region
        fields = ("id", "name", "order", "districts")


class MediaSerializer(ModelSerializer):
    """Read-only gallery representation with an absolute URL when possible."""

    image_url = SerializerMethodField()

    class Meta:
        model = Media
        fields = (
            "id",
            "image",
            "file",
            "image_url",
            "type",
            "is_main",
            "position",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "image_url")

    def get_image_url(self, obj: Media) -> Optional[str]:
        request = self.context.get("request")
        target = obj.image or obj.file
        if not target or not getattr(target, "name", None):
            return None
        url = target.url
        return request.build_absolute_uri(url) if request is not None else url


VenueImageSerializer = MediaSerializer


class BaseVenueSerializer(ModelSerializer):
    """Shared venue representation and multipart gallery handling."""

    owner_phone = ReadOnlyField(source="owner.phone_number")
    region_name = ReadOnlyField(source="region.name")
    district_name = ReadOnlyField(source="district.name")
    cover_image_url = SerializerMethodField()
    gallery_images = MediaSerializer(many=True, read_only=True)
    venue_fk_field = "hall"

    def get_cover_image_url(self, obj: Any) -> Optional[str]:
        request = self.context.get("request")
        if not obj.cover_image or not getattr(obj.cover_image, "name", None):
            return None
        url = obj.cover_image.url
        return request.build_absolute_uri(url) if request is not None else url

    def to_internal_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        mutable_data = data
        if "amenities" in data and isinstance(data["amenities"], str):
            mutable_data = data.copy()
            try:
                mutable_data["amenities"] = json.loads(data["amenities"])
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    {"amenities": "Amenities valid JSON formatida bo'lishi kerak."}
                ) from exc
        return super().to_internal_value(mutable_data)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        region = attrs.get("region", getattr(self.instance, "region", None))
        district = attrs.get("district", getattr(self.instance, "district", None))
        if region and district and district.region_id != region.id:
            raise ValidationError(
                {"district": "Tuman tanlangan viloyatga tegishli emas."}
            )
        amenities = attrs.get("amenities", getattr(self.instance, "amenities", []))
        if amenities is not None and not isinstance(amenities, list):
            raise ValidationError(
                {"amenities": "Amenities ro'yxat ko'rinishida bo'lishi kerak."}
            )
        return attrs

    def _process_gallery_uploads(self, instance: Any, request: Any) -> None:
        if request is None or not hasattr(request, "FILES"):
            return
        files = request.FILES.getlist("gallery_images")
        files += request.FILES.getlist("gallery_images[]")
        for uploaded_file in files:
            Media.objects.create(**{self.venue_fk_field: instance, "image": uploaded_file})

    @staticmethod
    def _delete_requested(data: Any) -> bool:
        return str(data).strip().lower() in {"true", "1", "yes"}

    def _delete_gallery_images(self, instance: Any, request: Any) -> None:
        if request is None or "deleted_gallery_ids" not in request.data:
            return
        raw_ids = request.data.get("deleted_gallery_ids")
        try:
            ids = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
            ids = [int(item) for item in ids] if isinstance(ids, list) else []
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError(
                {"deleted_gallery_ids": "Galereya IDlari ro'yxat bo'lishi kerak."}
            ) from exc
        if ids:
            Media.objects.filter(id__in=ids, **{self.venue_fk_field: instance}).delete()

    def create(self, validated_data: Dict[str, Any]) -> Any:
        request = self.context.get("request")
        if request is not None and "cover_image" in request.FILES:
            validated_data.setdefault("cover_image", request.FILES["cover_image"])
        instance = super().create(validated_data)
        self._process_gallery_uploads(instance, request)
        return instance

    def update(self, instance: Any, validated_data: Dict[str, Any]) -> Any:
        request = self.context.get("request")
        old_cover = instance.cover_image.name if instance.cover_image else None
        delete_cover = request is not None and self._delete_requested(
            request.data.get("delete_cover_image", False)
        )
        new_cover = request.FILES.get("cover_image") if request is not None else None

        if delete_cover and not new_cover:
            instance.cover_image = None
        if new_cover:
            validated_data["cover_image"] = new_cover
        instance = super().update(instance, validated_data)

        if (delete_cover or new_cover) and old_cover:
            # Delete the old storage object only after the database points at
            # the new value; failed writes do not destroy the current image.
            if old_cover != getattr(instance.cover_image, "name", None):
                instance.cover_image.storage.delete(old_cover)
        self._delete_gallery_images(instance, request)
        self._process_gallery_uploads(instance, request)
        return instance


class WeddingHallSerializer(BaseVenueSerializer):
    venue_fk_field = "hall"

    class Meta:
        model = WeddingHall
        fields = (
            "id",
            "owner",
            "owner_phone",
            "region",
            "region_name",
            "district",
            "district_name",
            "name",
            "address",
            "description",
            "max_capacity",
            "required_deposit",
            "cover_image",
            "cover_image_url",
            "video_url",
            "map_link",
            "amenities",
            "gallery_images",
            "created_at",
        )
        read_only_fields = ("id", "owner", "created_at", "cover_image_url", "gallery_images", "owner_phone", "region_name", "district_name")


class BarSerializer(BaseVenueSerializer):
    venue_fk_field = "bar"

    class Meta:
        model = Bar
        fields = (
            "id",
            "owner",
            "owner_phone",
            "region",
            "region_name",
            "district",
            "district_name",
            "name",
            "address",
            "description",
            "capacity",
            "price_per_hour",
            "required_deposit",
            "cover_image",
            "cover_image_url",
            "video_url",
            "map_link",
            "amenities",
            "gallery_images",
            "created_at",
        )
        read_only_fields = ("id", "owner", "created_at", "cover_image_url", "gallery_images", "owner_phone", "region_name", "district_name")


def _validate_hall_ownership(serializer: ModelSerializer, value: WeddingHall) -> WeddingHall:
    request = serializer.context.get("request")
    user = getattr(request, "user", None)
    if user and user.is_authenticated and not user.is_superuser:
        if getattr(user, "role", None) not in (CustomUser.Role.ADMIN, CustomUser.Role.VENUE_OWNER):
            raise ValidationError("Faqat joy egasi yoki admin bu resursni boshqarishi mumkin.")
        if getattr(user, "role", None) != CustomUser.Role.ADMIN and value.owner_id != user.id:
            raise ValidationError(
                "Siz faqat o'zingizga tegishli zal resurslarini o'zgartirishingiz mumkin."
            )
    return value


class ShiftSerializer(ModelSerializer):
    class Meta:
        model = Shift
        fields = ("id", "hall", "name", "start_time", "end_time", "is_active")
        read_only_fields = ("id",)

    def validate_hall(self, value: WeddingHall) -> WeddingHall:
        return _validate_hall_ownership(self, value)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        hall = attrs.get("hall", getattr(self.instance, "hall", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and start >= end:
            raise ValidationError(
                {"end_time": "Tugash vaqti boshlanish vaqtidan keyin bo'lishi shart."}
            )
        if hall:
            _validate_hall_ownership(self, hall)
        return attrs


class PackageSerializer(ModelSerializer):
    class Meta:
        model = Package
        fields = ("id", "hall", "guest_count", "price", "description")
        read_only_fields = ("id",)

    def validate_hall(self, value: WeddingHall) -> WeddingHall:
        return _validate_hall_ownership(self, value)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        hall = attrs.get("hall", getattr(self.instance, "hall", None))
        guest_count = attrs.get("guest_count", getattr(self.instance, "guest_count", None))
        if hall and guest_count and guest_count > hall.max_capacity:
            raise ValidationError(
                {"guest_count": "Mehmonlar soni zal sig'imidan oshmasligi kerak."}
            )
        return attrs


class DecorationSerializer(ModelSerializer):
    class Meta:
        model = Decoration
        fields = ("id", "hall", "name", "additional_price")
        read_only_fields = ("id",)

    def validate_hall(self, value: WeddingHall) -> WeddingHall:
        return _validate_hall_ownership(self, value)


class ShiftBlockSerializer(ModelSerializer):
    class Meta:
        model = ShiftBlock
        fields = ("id", "hall", "shift", "date", "reason")
        read_only_fields = ("id",)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        hall = attrs.get("hall", getattr(self.instance, "hall", None))
        shift = attrs.get("shift", getattr(self.instance, "shift", None))
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user and user.is_authenticated and not user.is_superuser:
            if getattr(user, "role", None) not in (CustomUser.Role.ADMIN, CustomUser.Role.VENUE_OWNER):
                raise ValidationError("Faqat joy egasi yoki admin smenani bloklashi mumkin.")
            if getattr(user, "role", None) != CustomUser.Role.ADMIN and hall and hall.owner_id != user.id:
                raise ValidationError(
                    {"hall": "Siz faqat o'zingizga tegishli zalni bloklay olasiz."}
                )
        if hall and shift and shift.hall_id != hall.id:
            raise ValidationError(
                {"shift": "Tanlangan smena ushbu zalga tegishli emas."}
            )
        return attrs
