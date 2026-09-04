from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from venues.models import Bar, ShiftBlock, WeddingHall
from .models import BarBooking, HallBooking
from .permissions import IsBookingManager, IsBookingParticipant
from .serializers import (
    BarBookingSerializer,
    BookingStatusSerializer,
    HallBookingSerializer,
    get_active_booking_q_filter,
)
from .services import cancel_booking, update_booking_status


def _get_role_filtered_booking_queryset(
    model_cls: Any,
    user: Any,
    select_related_fields: List[str],
    owner_filter_field: str,
):
    """Return only bookings visible to the current role."""

    if not user or not user.is_authenticated:
        return model_cls.objects.none()

    queryset = model_cls.objects.select_related(*select_related_fields).all()
    if user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
        return queryset
    if getattr(user, "role", None) == User.Role.VENUE_OWNER:
        return queryset.filter(**{owner_filter_field: user})
    return queryset.filter(user=user)


def _parse_year_month_params(request: Any) -> Tuple[Optional[int], Optional[int], Optional[Response]]:
    """Parse and validate calendar query parameters."""

    year_str = request.query_params.get("year")
    month_str = request.query_params.get("month")
    if not year_str or not month_str:
        return None, None, Response(
            {"error": "year va month query parametrlari kiritilishi shart."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        year = int(year_str)
        month = int(month_str)
    except (TypeError, ValueError):
        return None, None, Response(
            {"error": "year va month butun son bo'lishi shart."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (1 <= year <= 9999 and 1 <= month <= 12):
        return None, None, Response(
            {"error": "year 1-9999, month esa 1-12 oralig'ida bo'lishi shart."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return year, month, None


class HallBookingListCreateAPIView(APIView):
    serializer_class = HallBookingSerializer
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            HallBooking,
            self.request.user,
            ["user", "hall", "shift", "package", "decoration"],
            "hall__owner",
        )

    @extend_schema(
        tags=["Bookings"],
        summary="To'yxona bronlari ro'yxati",
        responses=HallBookingSerializer(many=True),
    )
    def get(self, request: Any) -> Response:
        serializer = HallBookingSerializer(
            self.get_queryset(), many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        tags=["Bookings"],
        summary="To'yxona uchun yangi bron so'rovi",
        request=HallBookingSerializer,
        responses=HallBookingSerializer,
    )
    def post(self, request: Any) -> Response:
        serializer = HallBookingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HallBookingDetailAPIView(APIView):
    serializer_class = HallBookingSerializer
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            HallBooking,
            self.request.user,
            ["user", "hall", "shift", "package", "decoration"],
            "hall__owner",
        )

    def get_object(self, pk: int) -> HallBooking:
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(tags=["Bookings"], summary="To'yxona broni tafsilotlari", responses=HallBookingSerializer)
    def get(self, request: Any, pk: int) -> Response:
        return Response(HallBookingSerializer(self.get_object(pk), context={"request": request}).data)

    @extend_schema(tags=["Bookings"], summary="To'yxona bronini yangilash", request=HallBookingSerializer, responses=HallBookingSerializer)
    def put(self, request: Any, pk: int) -> Response:
        return self._update(request, pk, partial=False)

    @extend_schema(tags=["Bookings"], summary="To'yxona bronini qisman yangilash", request=HallBookingSerializer, responses=HallBookingSerializer)
    def patch(self, request: Any, pk: int) -> Response:
        return self._update(request, pk, partial=True)

    def _update(self, request: Any, pk: int, partial: bool) -> Response:
        booking = self.get_object(pk)
        serializer = HallBookingSerializer(
            booking, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="To'yxona bronini bekor qilish")
    def delete(self, request: Any, pk: int) -> Response:
        cancel_booking(self.get_object(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BarBookingListCreateAPIView(APIView):
    serializer_class = BarBookingSerializer
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            BarBooking,
            self.request.user,
            ["user", "bar"],
            "bar__owner",
        )

    @extend_schema(tags=["Bookings"], summary="Bar bronlari ro'yxati", responses=BarBookingSerializer(many=True))
    def get(self, request: Any) -> Response:
        serializer = BarBookingSerializer(
            self.get_queryset(), many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="Bar uchun yangi bron so'rovi", request=BarBookingSerializer, responses=BarBookingSerializer)
    def post(self, request: Any) -> Response:
        serializer = BarBookingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BarBookingDetailAPIView(APIView):
    serializer_class = BarBookingSerializer
    permission_classes = [IsBookingParticipant]

    def get_queryset(self):
        return _get_role_filtered_booking_queryset(
            BarBooking,
            self.request.user,
            ["user", "bar"],
            "bar__owner",
        )

    def get_object(self, pk: int) -> BarBooking:
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(tags=["Bookings"], summary="Bar broni tafsilotlari", responses=BarBookingSerializer)
    def get(self, request: Any, pk: int) -> Response:
        return Response(BarBookingSerializer(self.get_object(pk), context={"request": request}).data)

    @extend_schema(tags=["Bookings"], summary="Bar bronini yangilash", request=BarBookingSerializer, responses=BarBookingSerializer)
    def put(self, request: Any, pk: int) -> Response:
        return self._update(request, pk, partial=False)

    @extend_schema(tags=["Bookings"], summary="Bar bronini qisman yangilash", request=BarBookingSerializer, responses=BarBookingSerializer)
    def patch(self, request: Any, pk: int) -> Response:
        return self._update(request, pk, partial=True)

    def _update(self, request: Any, pk: int, partial: bool) -> Response:
        booking = self.get_object(pk)
        serializer = BarBookingSerializer(
            booking, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(tags=["Bookings"], summary="Bar bronini bekor qilish")
    def delete(self, request: Any, pk: int) -> Response:
        cancel_booking(self.get_object(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class _BookingStatusAPIView(APIView):
    """Shared implementation for the public status route aliases."""

    permission_classes = [IsBookingManager]
    booking_model = None
    booking_serializer_class = None
    owner_filter_field = ""
    venue_relation = ""

    def get_queryset(self):
        queryset = self.booking_model.objects.select_related(
            "user", self.venue_relation
        )
        user = self.request.user
        if user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN:
            return queryset
        return queryset.filter(**{self.owner_filter_field: user})

    def get_object(self, pk: int):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    def patch(self, request: Any, pk: int) -> Response:
        booking = self.get_object(pk)
        payload = BookingStatusSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = update_booking_status(booking, payload.validated_data["status"])
        return Response(
            self.booking_serializer_class(updated, context={"request": request}).data
        )


class HallBookingStatusAPIView(_BookingStatusAPIView):
    serializer_class = BookingStatusSerializer
    booking_model = HallBooking
    booking_serializer_class = HallBookingSerializer
    owner_filter_field = "hall__owner"
    venue_relation = "hall"

    @extend_schema(
        tags=["Bookings"],
        operation_id="hall_booking_status_update",
        summary="To'yxona bron statusini o'zgartirish",
        request=BookingStatusSerializer,
        responses=HallBookingSerializer,
    )
    def patch(self, request: Any, pk: int) -> Response:
        return super().patch(request, pk)


class BarBookingStatusAPIView(_BookingStatusAPIView):
    serializer_class = BookingStatusSerializer
    booking_model = BarBooking
    booking_serializer_class = BarBookingSerializer
    owner_filter_field = "bar__owner"
    venue_relation = "bar"

    @extend_schema(
        tags=["Bookings"],
        operation_id="bar_booking_status_update",
        summary="Bar bron statusini o'zgartirish",
        request=BookingStatusSerializer,
        responses=BarBookingSerializer,
    )
    def patch(self, request: Any, pk: int) -> Response:
        return super().patch(request, pk)


_CALENDAR_PARAMETERS = [
    OpenApiParameter(
        name="year",
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description="Yil (masalan: 2026)",
        required=True,
    ),
    OpenApiParameter(
        name="month",
        type=OpenApiTypes.INT,
        location=OpenApiParameter.QUERY,
        description="Oy (1 dan 12 gacha)",
        required=True,
    ),
]


@extend_schema(
    tags=["Calendar"],
    summary="To'yxona taqvimi",
    parameters=_CALENDAR_PARAMETERS,
    responses={200: OpenApiTypes.OBJECT},
)
class HallCalendarView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Any, hall_id: int) -> Response:
        year, month, error_response = _parse_year_month_params(request)
        if error_response:
            return error_response
        hall = get_object_or_404(WeddingHall.objects.only("id"), pk=hall_id)

        bookings = (
            HallBooking.objects.filter(hall=hall, date__year=year, date__month=month)
            .filter(get_active_booking_q_filter())
            .select_related("shift")
        )
        blocks = ShiftBlock.objects.filter(
            hall=hall, date__year=year, date__month=month
        ).select_related("shift")

        busy_shifts: List[Dict[str, Any]] = [
            {
                "date": str(booking.date),
                "shift_id": booking.shift_id,
                "shift_name": booking.shift.name,
                "status": "BOOKED",
                "booking_status": booking.status,
            }
            for booking in bookings
        ]
        busy_shifts.extend(
            {
                "date": str(block.date),
                "shift_id": block.shift_id,
                "shift_name": block.shift.name,
                "status": "BLOCKED",
                "reason": block.reason,
            }
            for block in blocks
        )
        busy_shifts.sort(key=lambda item: (item["date"], item["shift_id"], item["status"]))

        return Response({"hall_id": hall.id, "year": year, "month": month, "busy_shifts": busy_shifts})


@extend_schema(
    tags=["Calendar"],
    summary="Bar bandlik taqvimi",
    parameters=_CALENDAR_PARAMETERS,
    responses={200: OpenApiTypes.OBJECT},
)
class BarCalendarView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Any, bar_id: int) -> Response:
        year, month, error_response = _parse_year_month_params(request)
        if error_response:
            return error_response
        bar = get_object_or_404(Bar.objects.only("id"), pk=bar_id)

        bookings = (
            BarBooking.objects.filter(bar=bar, date__year=year, date__month=month)
            .filter(get_active_booking_q_filter())
            .order_by("date", "start_time")
        )
        busy_slots = [
            {
                "date": str(booking.date),
                "start_time": str(booking.start_time),
                "end_time": str(booking.end_time),
                "status": "BOOKED",
                "booking_status": booking.status,
            }
            for booking in bookings
        ]
        return Response({"bar_id": bar.id, "year": year, "month": month, "busy_slots": busy_slots})
