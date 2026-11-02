from datetime import datetime, timedelta, timezone as dt_timezone
import secrets
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from bookings.models import BarBooking, HallBooking
from telegram_bot.permissions import IsPlatformAdmin
from venues.models import Bar, Region, WeddingHall

from .models import TelegramAuthSession
from .serializers import AdminUserSerializer, PhoneTokenObtainPairSerializer, UserSerializer

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


def get_bot_username() -> str:
    from telegram_bot.models import TelegramBotConfig
    try:
        config = TelegramBotConfig.load()
        if config and config.bot_username:
            return config.bot_username.lstrip("@").strip()
    except Exception:
        pass
    return getattr(settings, "TELEGRAM_BOT_USERNAME", "").lstrip("@").strip()


@extend_schema(tags=["Telegram Auth"], summary="Telegram orqali kirish sessiyasini boshlash")
class TelegramAuthInitView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        session_id = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=3)
        TelegramAuthSession.objects.create(
            session_id=session_id,
            expires_at=expires_at,
        )

        bot_username = get_bot_username()
        bot_url = f"https://t.me/{bot_username}?start=auth_{session_id}" if bot_username else ""

        return Response({
            "session_id": session_id,
            "bot_username": bot_username,
            "bot_url": bot_url,
            "expires_at": expires_at.isoformat(),
            "expires_in_seconds": 180,
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Telegram Auth"], summary="Telegram auth sessiyasi holatini tekshirish")
class TelegramAuthStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, session_id, *args, **kwargs):
        session = TelegramAuthSession.objects.filter(session_id=session_id).first()
        if not session:
            return Response(
                {"status": "NOT_FOUND", "detail": "Sessiya topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if session.status == TelegramAuthSession.Status.COMPLETED:
            return Response(
                {"status": "COMPLETED", "detail": "Ushbu sessiya allaqachon yakunlangan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if session.is_expired():
            if session.status != TelegramAuthSession.Status.EXPIRED:
                session.status = TelegramAuthSession.Status.EXPIRED
                session.save(update_fields=["status"])
            return Response({"status": "EXPIRED", "detail": "Sessiya muddati tugagan."})

        if session.status == TelegramAuthSession.Status.PENDING:
            return Response({"status": "PENDING"})

        if session.status == TelegramAuthSession.Status.AUTHENTICATED:
            user = session.user
            if not user or not user.is_active:
                return Response(
                    {"status": "FAILED", "detail": "Foydalanuvchi hisobi faol emas."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            refresh = RefreshToken.for_user(user)

            # Prevent replay attacks
            session.status = TelegramAuthSession.Status.COMPLETED
            session.save(update_fields=["status"])

            return Response({
                "status": "AUTHENTICATED",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new_user": session.is_new_user,
                "user": UserSerializer(user).data,
            })

        return Response({"status": session.status})


@extend_schema(tags=["Telegram Auth"], summary="Yangi ro'yxatdan o'tgan foydalanuvchi profil ma'lumotlarini to'ldirish (Rol va Ism)")
class CompleteProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        role = request.data.get("role")
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()

        allowed_roles = [User.Role.CLIENT, User.Role.VENUE_OWNER]
        updated_fields = []

        if role and role in allowed_roles:
            user.role = role
            updated_fields.append("role")

        if first_name:
            user.first_name = first_name
            updated_fields.append("first_name")

        if last_name:
            user.last_name = last_name
            updated_fields.append("last_name")

        if updated_fields:
            user.save(update_fields=updated_fields)

        return Response({
            "message": "Profil muvaffaqiyatli yangilandi.",
            "user": UserSerializer(user).data,
        })

