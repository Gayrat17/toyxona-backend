from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import normalize_phone_number

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the current user's public profile."""

    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "first_name",
            "last_name",
            "role",
            "is_verified",
            "email",
        )
        read_only_fields = ("id", "role", "is_verified")

    def validate_phone_number(self, value: str) -> str:
        try:
            return normalize_phone_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class PhoneTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Accept the same local phone formats as registration and profile APIs."""

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        phone_field = self.username_field
        try:
            attrs[phone_field] = normalize_phone_number(attrs[phone_field])
        except ValueError as exc:
            raise serializers.ValidationError({phone_field: str(exc)}) from exc
        return super().validate(attrs)


class UserCreateSerializer(serializers.ModelSerializer):
    """Register a client or venue owner; administrators are never self-created."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "password",
            "first_name",
            "last_name",
            "email",
            "role",
        )
        read_only_fields = ("id",)

    def validate_phone_number(self, value: str) -> str:
        try:
            return normalize_phone_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_role(self, value: str) -> str:
        if value not in {User.Role.CLIENT, User.Role.VENUE_OWNER}:
            raise serializers.ValidationError(
                "Ro'yxatdan o'tishda faqat CLIENT yoki VENUE_OWNER roli tanlanishi mumkin."
            )
        return value

    def create(self, validated_data: Dict[str, Any]) -> User:
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)
