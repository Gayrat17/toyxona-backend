from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import PhoneTokenObtainPairSerializer


class PhoneTokenObtainPairView(TokenObtainPairView):
    """Issue JWTs after normalizing the supplied phone number."""

    serializer_class = PhoneTokenObtainPairSerializer
