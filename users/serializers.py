from typing import Dict, Any
from adrf.serializers import ModelSerializer
from rest_framework.serializers import CharField
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(ModelSerializer):
    """
    Serializer for retrieving and updating user profiles.
    """
    class Meta:
        model = User
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'role', 'is_verified', 'email')
        read_only_fields = ('role', 'is_verified')


class UserCreateSerializer(ModelSerializer):
    """
    Serializer for registering new users.
    """
    password = CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'phone_number', 'password', 'first_name', 'last_name', 'role')

    def create(self, validated_data: Dict[str, Any]) -> Any:
        """
        Creates a new user account while enforcing allowed role registration.
        """
        role = validated_data.get('role', User.Role.CLIENT)
        
        # Prevent unauthorized registration as ADMIN
        allowed_registration_roles = {User.Role.CLIENT, User.Role.VENUE_OWNER}
        if role not in allowed_registration_roles:
            role = User.Role.CLIENT

        return User.objects.create_user(
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=role
        )

