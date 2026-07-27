from typing import Tuple, Optional, Any, Dict, List
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, QuerySet
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.shortcuts import get_object_or_404

from users.models import User
from venues.models import ShiftBlock
from .models import HallBooking, BarBooking, BaseBooking
from .serializers import HallBookingSerializer, BarBookingSerializer, get_active_booking_q_filter
from .permissions import IsBookingParticipant


def _get_role_filtered_booking_queryset(
    model_cls: Any, 
    user: Any, 
    select_related_fields: List[str], 
    owner_filter_field: str
) -> QuerySet:
    """
    Filters booking queryset depending on user role:
    - Anonymous: returns none
    - Admin/Superuser: returns all records
    - Venue owner: returns bookings belonging to their venues
    - Client: returns bookings initiated by themselves
    """
    if not user or not user.is_authenticated:
        return model_cls.objects.none()

    qs = model_cls.objects.select_related(*select_related_fields).all()

    if user.is_superuser or getattr(user, 'role', None) == User.Role.ADMIN:
        return qs

    if getattr(user, 'role', None) == User.Role.VENUE_OWNER:
        return qs.filter(**{owner_filter_field: user})

    return qs.filter(user=user)


def _parse_year_month_params(request: Any) -> Tuple[Optional[int], Optional[int], Optional[Response]]:
    """
    Parses and validates year and month query parameters.
    Returns (year, month, error_response).
    """
    year_str = request.query_params.get('year')
    month_str = request.query_params.get('month')

    if not year_str or not month_str:
        return None, None, Response(
            {"error": "year va month query parametrlari kiritilishi shart."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        year = int(year_str)
        month = int(month_str)
        if not (1 <= month <= 12):
            raise ValueError("Month range invalid")
        return year, month, None
    except ValueError:
        return None, None, Response(
            {"error": "year va month butun son bo'lishi va oy 1-12 oralig'ida bo'lishi shart."},
            status=status.HTTP_400_BAD_REQUEST
        )


class HallBookingListCreateAPIView(APIView):
    """
    To'yxonalar uchun bron qilish xizmati. 
    Mijozlar faqat o'z bronlarini ko'ra olishadi, To'yxona egalari esa o'z zallariga tegishli bronlarni ko'radi.
    """
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            model_cls=HallBooking,
            user=self.request.user,
            select_related_fields=['user', 'hall', 'shift', 'package', 'decoration'],
            owner_filter_field='hall__owner'
        )

    @extend_schema(tags=["Bookings"], summary="To'yxona bronlari ro'yxatini olish (Rollar bo'yicha filtrlanadi)", responses=HallBookingSerializer(many=True))
    def get(self, request: Any) -> Response:
        qs = self.get_queryset()
        serializer = HallBookingSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="To'yxona uchun yangi bron so'rovi yuborish (Avtomat narxlanadi)", request=HallBookingSerializer, responses=HallBookingSerializer)
    def post(self, request: Any) -> Response:
        serializer = HallBookingSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HallBookingDetailAPIView(APIView):
    """
    To'yxonalar uchun bron tafsilotlari.
    """
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            model_cls=HallBooking,
            user=self.request.user,
            select_related_fields=['user', 'hall', 'shift', 'package', 'decoration'],
            owner_filter_field='hall__owner'
        )

    def get_object(self, pk: int):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(tags=["Bookings"], summary="To'yxona broni tafsilotlarini olish", responses=HallBookingSerializer)
    def get(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        serializer = HallBookingSerializer(obj, context={'request': request})
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="To'yxona broni ma'lumotlarini to'liq yangilash", request=HallBookingSerializer, responses=HallBookingSerializer)
    def put(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        serializer = HallBookingSerializer(obj, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="To'yxona broni ma'lumotlarini qisman yangilash", request=HallBookingSerializer, responses=HallBookingSerializer)
    def patch(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        serializer = HallBookingSerializer(obj, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="To'yxona bronini o'chirish/bekor qilish")
    def delete(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BarBookingListCreateAPIView(APIView):
    """
    Barlar uchun soatlik bron qilish xizmati.
    """
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            model_cls=BarBooking,
            user=self.request.user,
            select_related_fields=['user', 'bar'],
            owner_filter_field='bar__owner'
        )

    @extend_schema(tags=["Bookings"], summary="Bar bronlari ro'yxatini olish (Rollar bo'yicha filtrlanadi)", responses=BarBookingSerializer(many=True))
    def get(self, request: Any) -> Response:
        qs = self.get_queryset()
        serializer = BarBookingSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="Bar uchun yangi bron so'rovi yuborish (Avtomat narxlanadi)", request=BarBookingSerializer, responses=BarBookingSerializer)
    def post(self, request: Any) -> Response:
        serializer = BarBookingSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BarBookingDetailAPIView(APIView):
    """
    Barlar uchun bron tafsilotlari.
    """
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            model_cls=BarBooking,
            user=self.request.user,
            select_related_fields=['user', 'bar'],
            owner_filter_field='bar__owner'
        )

    def get_object(self, pk: int):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(tags=["Bookings"], summary="Bar broni tafsilotlarini olish", responses=BarBookingSerializer)
    def get(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        serializer = BarBookingSerializer(obj, context={'request': request})
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="Bar broni ma'lumotlarini to'liq yangilash", request=BarBookingSerializer, responses=BarBookingSerializer)
    def put(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        serializer = BarBookingSerializer(obj, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="Bar broni ma'lumotlarini qisman yangilash", request=BarBookingSerializer, responses=BarBookingSerializer)
    def patch(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        serializer = BarBookingSerializer(obj, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="Bar bronini o'chirish/bekor qilish")
    def delete(self, request: Any, pk: int) -> Response:
        obj = self.get_object(pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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

    def get(self, request: Any, hall_id: int) -> Response:
        year, month, error_response = _parse_year_month_params(request)
        if error_response:
            return error_response

        bookings = HallBooking.objects.filter(
            hall_id=hall_id,
            date__year=year,
            date__month=month
        ).filter(get_active_booking_q_filter()).select_related('shift')

        blocks = ShiftBlock.objects.filter(
            hall_id=hall_id,
            date__year=year,
            date__month=month
        ).select_related('shift')

        busy_shifts: List[Dict[str, Any]] = []

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

    def get(self, request: Any, bar_id: int) -> Response:
        year, month, error_response = _parse_year_month_params(request)
        if error_response:
            return error_response

        bookings = BarBooking.objects.filter(
            bar_id=bar_id,
            date__year=year,
            date__month=month
        ).filter(get_active_booking_q_filter())

        busy_slots: List[Dict[str, Any]] = []

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
