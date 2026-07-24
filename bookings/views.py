from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from venues.models import ShiftBlock
from .models import HallBooking, BarBooking
from .serializers import HallBookingSerializer, BarBookingSerializer
from .permissions import IsBookingParticipant

@extend_schema_view(
    list=extend_schema(summary="To'yxona bronlari ro'yxatini olish (Rollar bo'yicha filtrlanadi)"),
    retrieve=extend_schema(summary="To'yxona broni tafsilotlarini olish"),
    create=extend_schema(summary="To'yxona uchun yangi bron so'rovi yuborish (Avtomat narxlanadi)"),
    update=extend_schema(summary="To'yxona broni ma'lumotlarini to'liq yangilash"),
    partial_update=extend_schema(summary="To'yxona broni ma'lumotlarini qisman yangilash"),
    destroy=extend_schema(summary="To'yxona bronini o'chirish/bekor qilish"),
)
@extend_schema(tags=["Bookings"])
class HallBookingViewSet(viewsets.ModelViewSet):
    """
    To'yxonalar uchun bron qilish xizmati. 
    Mijozlar faqat o'z bronlarini ko'ra olishadi, To'yxona egalari esa o'z zallariga tegishli bronlarni ko'radi.
    """
    serializer_class = HallBookingSerializer
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return HallBooking.objects.none()

        if user.is_superuser or user.role == 'ADMIN':
            return HallBooking.objects.select_related('user', 'hall', 'shift', 'package', 'decoration').all()

        if user.role == 'VENUE_OWNER':
            return HallBooking.objects.select_related('user', 'hall', 'shift', 'package', 'decoration').filter(hall__owner=user)

        return HallBooking.objects.select_related('user', 'hall', 'shift', 'package', 'decoration').filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="Bar bronlari ro'yxatini olish (Rollar bo'yicha filtrlanadi)"),
    retrieve=extend_schema(summary="Bar broni tafsilotlarini olish"),
    create=extend_schema(summary="Bar uchun yangi bron so'rovi yuborish (Avtomat narxlanadi)"),
    update=extend_schema(summary="Bar broni ma'lumotlarini to'liq yangilash"),
    partial_update=extend_schema(summary="Bar broni ma'lumotlarini qisman yangilash"),
    destroy=extend_schema(summary="Bar bronini o'chirish/bekor qilish"),
)
@extend_schema(tags=["Bookings"])
class BarBookingViewSet(viewsets.ModelViewSet):
    """
    Barlar uchun soatlik bron qilish xizmati.
    """
    serializer_class = BarBookingSerializer
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return BarBooking.objects.none()

        if user.is_superuser or user.role == 'ADMIN':
            return BarBooking.objects.select_related('user', 'bar').all()

        if user.role == 'VENUE_OWNER':
            return BarBooking.objects.select_related('user', 'bar').filter(bar__owner=user)

        return BarBooking.objects.select_related('user', 'bar').filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema(
    tags=["Calendar"],
    summary="To'yxona taqvimi (Band va blok kunlar)",
    description="Berilgan to'yxona (hall_id) uchun tanlangan yil va oydagi barcha band bronlar va bloklangan smenalarni qaytaradi.",
    parameters=[
        OpenApiParameter(name='year', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='Yil (masalan: 2026)', required=True),
        OpenApiParameter(name='month', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='Oy (1 dan 12 gacha, masalan: 8)', required=True),
    ],
    responses={200: OpenApiTypes.OBJECT}
)
class HallCalendarView(APIView):
    """
    Public endpoint to view occupied and admin-blocked dates/shifts for a wedding hall.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, hall_id):
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not year or not month:
            return Response(
                {"error": "year va month query parametrlari kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            year = int(year)
            month = int(month)
        except ValueError:
            return Response(
                {"error": "year va month butun son bo'lishi shart."},
                status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()
        
        bookings = HallBooking.objects.filter(
            hall_id=hall_id,
            date__year=year,
            date__month=month
        ).filter(
            Q(status__in=['PENDING', 'CONFIRMED']) |
            Q(status='HOLD', expires_at__gt=now) |
            Q(status='HOLD', expires_at__isnull=True)
        ).select_related('shift')

        blocks = ShiftBlock.objects.filter(
            hall_id=hall_id,
            date__year=year,
            date__month=month
        ).select_related('shift')

        busy_shifts = []

        for booking in bookings:
            busy_shifts.append({
                "date": str(booking.date),
                "shift_id": booking.shift.id,
                "shift_name": booking.shift.name,
                "status": "BOOKED",
                "booking_status": booking.status
            })

        for block in blocks:
            busy_shifts.append({
                "date": str(block.date),
                "shift_id": block.shift.id,
                "shift_name": block.shift.name,
                "status": "BLOCKED",
                "reason": block.reason
            })

        busy_shifts.sort(key=lambda x: x['date'])

        return Response({
            "hall_id": hall_id,
            "year": year,
            "month": month,
            "busy_shifts": busy_shifts
        })


@extend_schema(
    tags=["Calendar"],
    summary="Bar bandlik taqvimi (Band soatlar)",
    description="Berilgan bar (bar_id) uchun tanlangan yil va oydagi barcha band bron qilingan kunlik soat intervallarini qaytaradi.",
    parameters=[
        OpenApiParameter(name='year', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='Yil (masalan: 2026)', required=True),
        OpenApiParameter(name='month', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description='Oy (1 dan 12 gacha, masalan: 8)', required=True),
    ],
    responses={200: OpenApiTypes.OBJECT}
)
class BarCalendarView(APIView):
    """
    Public endpoint to view occupied hours for an hourly bar booking calendar.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, bar_id):
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not year or not month:
            return Response(
                {"error": "year va month query parametrlari kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            year = int(year)
            month = int(month)
        except ValueError:
            return Response(
                {"error": "year va month butun son bo'lishi shart."},
                status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()
        
        bookings = BarBooking.objects.filter(
            bar_id=bar_id,
            date__year=year,
            date__month=month
        ).filter(
            Q(status__in=['PENDING', 'CONFIRMED']) |
            Q(status='HOLD', expires_at__gt=now) |
            Q(status='HOLD', expires_at__isnull=True)
        )

        busy_slots = []

        for booking in bookings:
            busy_slots.append({
                "date": str(booking.date),
                "start_time": str(booking.start_time),
                "end_time": str(booking.end_time),
                "status": "BOOKED",
                "booking_status": booking.status
            })

        busy_slots.sort(key=lambda x: (x['date'], x['start_time']))

        return Response({
            "bar_id": bar_id,
            "year": year,
            "month": month,
            "busy_slots": busy_slots
        })
