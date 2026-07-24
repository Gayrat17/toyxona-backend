from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving and updating user profiles.
    """
    class Meta:
        model = User
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'role', 'is_verified', 'email')
        read_only_fields = ('role', 'is_verified')

class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for registering new users.
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'phone_number', 'password', 'first_name', 'last_name', 'role')

    def create(self, validated_data):
        # Default role is CLIENT if not explicitly provided or invalid
        role = validated_data.get('role', 'CLIENT')
        if role not in ['CLIENT', 'VENUE_OWNER']:
            role = 'CLIENT'  # Prevent arbitrary admin registration

        user = User.objects.create_user(
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=role
        )
        return user
