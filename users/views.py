from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from bookings.models import BarBooking, HallBooking
from telegram_bot.permissions import IsPlatformAdmin
from venues.models import Bar, Region, WeddingHall

from .serializers import AdminUserSerializer, PhoneTokenObtainPairSerializer

User = get_user_model()


class PhoneTokenObtainPairView(TokenObtainPairView):
    """Issue JWTs after normalizing the supplied phone number with strict rate limiting."""

    serializer_class = PhoneTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class AdminUserListAPIView(generics.ListAPIView):
    """List all registered users for administrators."""

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]


class AdminUserDetailAPIView(generics.RetrieveUpdateAPIView):
    """View and update user status (e.g. is_active) for administrators."""

    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]


@extend_schema(tags=["Stats"], summary="Platforma statistikasi (Ommaviy/Admin)")
class PlatformStatsAPIView(APIView):
    """
    Computes real platform statistics across users, venues, and bookings.
    Calculates live metrics with zero mock values.
    Public visitors receive public venue/booking counts; financial revenue
    and deposits are strictly restricted to platform administrators.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        # Public aggregate counts
        total_users = User.objects.count()
        total_halls = WeddingHall.objects.count()
        total_bars = Bar.objects.count()
        active_venues = total_halls + total_bars
        total_regions = Region.objects.count()

        # Bookings counts
        total_hall_bookings = HallBooking.objects.count()
        total_bar_bookings = BarBooking.objects.count()
        total_bookings = total_hall_bookings + total_bar_bookings

        # Current month bookings
        start_of_month = datetime(current_year, current_month, 1, tzinfo=dt_timezone.utc)
        monthly_hall_bookings = HallBooking.objects.filter(created_at__gte=start_of_month).count()
        monthly_bar_bookings = BarBooking.objects.filter(created_at__gte=start_of_month).count()
        monthly_bookings = monthly_hall_bookings + monthly_bar_bookings

        # Sensitive financial metrics: Only platform administrators are permitted to see revenue
        is_admin = bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or getattr(request.user, "role", None) == User.Role.ADMIN)
        )

        total_revenue = "0"
        total_deposits = "0"
        monthly_growth = []

        if is_admin:
            hall_revenue = HallBooking.objects.aggregate(total=Sum("total_price"))["total"] or Decimal("0")
            bar_revenue = BarBooking.objects.aggregate(total=Sum("total_price"))["total"] or Decimal("0")
            total_revenue = str(hall_revenue + bar_revenue)

            hall_deposits = HallBooking.objects.aggregate(total=Sum("deposit_amount"))["total"] or Decimal("0")
            bar_deposits = BarBooking.objects.aggregate(total=Sum("deposit_amount"))["total"] or Decimal("0")
            total_deposits = str(hall_deposits + bar_deposits)

            month_names_uz = [
                "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
                "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"
            ]

            for i in range(5, -1, -1):
                target_month = current_month - i
                target_year = current_year
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                count_halls = HallBooking.objects.filter(
                    created_at__year=target_year,
                    created_at__month=target_month
                ).count()
                count_bars = BarBooking.objects.filter(
                    created_at__year=target_year,
                    created_at__month=target_month
                ).count()
                month_count = count_halls + count_bars

                monthly_growth.append({
                    "month": month_names_uz[target_month - 1],
                    "year": target_year,
                    "count": month_count,
                })

        return Response({
            "total_users": total_users,
            "active_venues": active_venues,
            "total_halls": total_halls,
            "total_bars": total_bars,
            "total_regions": total_regions,
            "total_bookings": total_bookings,
            "monthly_bookings": monthly_bookings,
            "total_revenue": total_revenue,
            "total_deposits": total_deposits,
            "monthly_growth": monthly_growth,
        })
