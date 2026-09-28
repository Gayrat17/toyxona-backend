from typing import Any

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, SAFE_METHODS
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_spectacular.utils import extend_schema

from users.models import User
from .models import Region, District, WeddingHall, Bar, Shift, Package, Decoration, ShiftBlock
from .serializers import (
    RegionSerializer,
    DistrictSerializer,
    WeddingHallSerializer,
    BarSerializer,
    ShiftSerializer,
    PackageSerializer,
    DecorationSerializer,
    ShiftBlockSerializer,
)
from .permissions import IsOwnerOrReadOnly, IsPlatformAdmin


class VenuePagination(PageNumberPagination):
    """Standard pagination for venue list endpoints."""
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 48


# =====================================================================
# Helper Functions
# =====================================================================

def _is_truthy_query_param(value: Any) -> bool:
    """Helper to check if query parameter string represents truthy value."""
    if not value:
        return False
    return str(value).strip().lower() in {'true', '1', 'yes'}


def _apply_venue_filters(queryset, request, model_class):
    """
    Apply common venue filters shared between WeddingHall and Bar list views.
    Supports: my_venues, region, district, search/q, min_capacity.
    """
    params = request.query_params
    my_venues = params.get('my_venues')

    if _is_truthy_query_param(my_venues):
        user = request.user
        if user and user.is_authenticated:
            if user.is_superuser or getattr(user, 'role', None) == User.Role.ADMIN:
                pass
            else:
                queryset = queryset.filter(owner=user)
        else:
            return queryset.none()

    # 1. Filter by region (ID or Name)
    region_param = params.get('region')
    if region_param:
        if str(region_param).isdigit():
            region_obj = Region.objects.filter(id=int(region_param)).first()
            if region_obj:
                clean_name = region_obj.name.replace(" viloyati", "").replace(" shahri", "").strip()
                queryset = queryset.filter(
                    Q(region_id=int(region_param)) | 
                    Q(address__icontains=region_obj.name) |
                    Q(address__icontains=clean_name)
                )
            else:
                queryset = queryset.filter(region_id=int(region_param))
        else:
            queryset = queryset.filter(
                Q(region__name__icontains=region_param) | Q(address__icontains=region_param)
            )

    # 2. Filter by district (ID or Name)
    district_param = params.get('district')
    if district_param:
        if str(district_param).isdigit():
            district_obj = District.objects.filter(id=int(district_param)).first()
            if district_obj:
                clean_dist_name = district_obj.name.replace(" tumani", "").replace(" shahri", "").replace(" sh.", "").strip()
                queryset = queryset.filter(
                    Q(district_id=int(district_param)) | 
                    Q(address__icontains=district_obj.name) |
                    Q(address__icontains=clean_dist_name)
                )
            else:
                queryset = queryset.filter(district_id=int(district_param))
        else:
            queryset = queryset.filter(
                Q(district__name__icontains=district_param) | Q(address__icontains=district_param)
            )

    # 3. Filter by search text (name or address)
    search_param = params.get('search') or params.get('q')
    if search_param:
        queryset = queryset.filter(
            Q(name__icontains=search_param) | Q(address__icontains=search_param)
        )

    # 4. Filter by minimum capacity
    min_capacity = params.get('min_capacity')
    if min_capacity and str(min_capacity).isdigit():
        min_cap_int = int(min_capacity)
        if hasattr(model_class, 'max_capacity'):
            queryset = queryset.filter(max_capacity__gte=min_cap_int)
        elif hasattr(model_class, 'capacity'):
            queryset = queryset.filter(capacity__gte=min_cap_int)

    return queryset


# =====================================================================
# Region Views
# =====================================================================

@extend_schema(tags=["Regions"])
class RegionListCreateAPIView(APIView):
    """
    GET  — Barcha viloyatlar ro'yxatini olish (tumanlar bilan birga).
    POST — Yangi viloyat qo'shish (Faqat Admin).
    """
    serializer_class = RegionSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsPlatformAdmin()]

    @extend_schema(operation_id="region_list", summary="Barcha viloyatlar ro'yxatini olish")
    def get(self, request):
        regions = Region.objects.prefetch_related('districts').all()
        serializer = RegionSerializer(regions, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi viloyat qo'shish (Faqat Admin)")
    def post(self, request):
        serializer = RegionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Regions"])
class RegionDetailAPIView(APIView):
    """
    GET    — Viloyat tafsilotlarini olish.
    PUT    — Viloyat ma'lumotlarini to'liq yangilash.
    PATCH  — Viloyat ma'lumotlarini qisman yangilash.
    DELETE — Viloyatni o'chirish.
    """
    serializer_class = RegionSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsPlatformAdmin()]

    def get_object(self, pk):
        obj = get_object_or_404(Region.objects.prefetch_related('districts'), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="region_detail", summary="Viloyat tafsilotlarini olish")
    def get(self, request, pk):
        region = self.get_object(pk)
        serializer = RegionSerializer(region, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Viloyat ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        region = self.get_object(pk)
        serializer = RegionSerializer(region, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Viloyat ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        region = self.get_object(pk)
        serializer = RegionSerializer(region, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Viloyatni o'chirish")
    def delete(self, request, pk):
        region = self.get_object(pk)
        region.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# District Views
# =====================================================================

@extend_schema(tags=["Districts"])
class DistrictListCreateAPIView(APIView):
    """
    GET  — Barcha tumanlar ro'yxati (?region=<id> filter mavjud).
    POST — Yangi tuman qo'shish (Faqat Admin).
    """
    serializer_class = DistrictSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsPlatformAdmin()]

    @extend_schema(operation_id="district_list", summary="Barcha tumanlar ro'yxatini olish (region bo'yicha filter)")
    def get(self, request):
        queryset = District.objects.select_related('region').all()
        region_id = request.query_params.get('region')
        if region_id:
            queryset = queryset.filter(region_id=region_id)
        serializer = DistrictSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi tuman qo'shish (Faqat Admin)")
    def post(self, request):
        serializer = DistrictSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Districts"])
class DistrictDetailAPIView(APIView):
    """
    GET    — Tuman tafsilotlarini olish.
    PUT    — Tuman ma'lumotlarini to'liq yangilash.
    PATCH  — Tuman ma'lumotlarini qisman yangilash.
    DELETE — Tumanni o'chirish.
    """
    serializer_class = DistrictSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsPlatformAdmin()]

    def get_object(self, pk):
        obj = get_object_or_404(District.objects.select_related('region'), pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="district_detail", summary="Tuman tafsilotlarini olish")
    def get(self, request, pk):
        district = self.get_object(pk)
        serializer = DistrictSerializer(district, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Tuman ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        district = self.get_object(pk)
        serializer = DistrictSerializer(district, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Tuman ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        district = self.get_object(pk)
        serializer = DistrictSerializer(district, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Tumanni o'chirish")
    def delete(self, request, pk):
        district = self.get_object(pk)
        district.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# WeddingHall Views
# =====================================================================

@extend_schema(tags=["Wedding Halls"])
class WeddingHallListCreateAPIView(APIView):
    """
    GET  — Barcha to'yxonalar ro'yxati (my_venues, region, district, search, min_capacity filtrlari).
    POST — Yangi to'yxona qo'shish (Faqat Joy egalari).
    """
    serializer_class = WeddingHallSerializer
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(operation_id="wedding_hall_list", summary="Barcha to'yxonalar ro'yxatini olish (my_venues=true bo'lsa faqat o'zinikini)")
    def get(self, request):
        queryset = WeddingHall.objects.select_related(
            'owner', 'region', 'district'
        ).prefetch_related('gallery_images').all()
        queryset = _apply_venue_filters(queryset, request, WeddingHall)
        paginator = VenuePagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = WeddingHallSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        serializer = WeddingHallSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi to'yxona qo'shish (Faqat Joy egalari)")
    def post(self, request):
        serializer = WeddingHallSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Wedding Halls"])
class WeddingHallDetailAPIView(APIView):
    """
    GET    — To'yxona tafsilotlarini olish.
    PUT    — To'yxona ma'lumotlarini to'liq yangilash.
    PATCH  — To'yxona ma'lumotlarini qisman yangilash.
    DELETE — To'yxonani o'chirish.
    """
    serializer_class = WeddingHallSerializer
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self, pk):
        obj = get_object_or_404(
            WeddingHall.objects.select_related('owner', 'region', 'district').prefetch_related('gallery_images'),
            pk=pk,
        )
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="wedding_hall_detail", summary="To'yxona tafsilotlarini olish")
    def get(self, request, pk):
        hall = self.get_object(pk)
        serializer = WeddingHallSerializer(hall, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="To'yxona ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        hall = self.get_object(pk)
        serializer = WeddingHallSerializer(hall, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        if getattr(hall, 'owner', None) is None:
            serializer.save(owner=request.user)
        else:
            serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="To'yxona ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        hall = self.get_object(pk)
        serializer = WeddingHallSerializer(hall, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        if getattr(hall, 'owner', None) is None:
            serializer.save(owner=request.user)
        else:
            serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="To'yxonani o'chirish")
    def delete(self, request, pk):
        hall = self.get_object(pk)
        hall.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# Bar Views
# =====================================================================

@extend_schema(tags=["Bars"])
class BarListCreateAPIView(APIView):
    """
    GET  — Barcha barlar ro'yxati (my_venues, region, district, search, min_capacity filtrlari).
    POST — Yangi bar qo'shish (Faqat Joy egalari).
    """
    serializer_class = BarSerializer
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(operation_id="bar_list", summary="Barcha barlar ro'yxatini olish (my_venues=true bo'lsa faqat o'zinikini)")
    def get(self, request):
        queryset = Bar.objects.select_related(
            'owner', 'region', 'district'
        ).prefetch_related('gallery_images').all()
        queryset = _apply_venue_filters(queryset, request, Bar)
        paginator = VenuePagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = BarSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        serializer = BarSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi bar qo'shish (Faqat Joy egalari)")
    def post(self, request):
        serializer = BarSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Bars"])
class BarDetailAPIView(APIView):
    """
    GET    — Bar tafsilotlarini olish.
    PUT    — Bar ma'lumotlarini to'liq yangilash.
    PATCH  — Bar ma'lumotlarini qisman yangilash.
    DELETE — Barni o'chirish.
    """
    serializer_class = BarSerializer
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self, pk):
        obj = get_object_or_404(
            Bar.objects.select_related('owner', 'region', 'district').prefetch_related('gallery_images'),
            pk=pk,
        )
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="bar_detail", summary="Bar tafsilotlarini olish")
    def get(self, request, pk):
        bar = self.get_object(pk)
        serializer = BarSerializer(bar, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Bar ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        bar = self.get_object(pk)
        serializer = BarSerializer(bar, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        if getattr(bar, 'owner', None) is None:
            serializer.save(owner=request.user)
        else:
            serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Bar ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        bar = self.get_object(pk)
        serializer = BarSerializer(bar, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        if getattr(bar, 'owner', None) is None:
            serializer.save(owner=request.user)
        else:
            serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Barni o'chirish")
    def delete(self, request, pk):
        bar = self.get_object(pk)
        bar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# Shift Views
# =====================================================================

@extend_schema(tags=["Shifts"])
class ShiftListCreateAPIView(APIView):
    """
    GET  — Smenalar ro'yxati (?hall=<id> filter mavjud).
    POST — Yangi smena qo'shish.
    """
    serializer_class = ShiftSerializer
    permission_classes = [IsOwnerOrReadOnly]

    @extend_schema(operation_id="shift_list", summary="Smenalar ro'yxatini olish (hall bo'yicha filter)")
    def get(self, request):
        queryset = Shift.objects.all()
        hall_id = request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        serializer = ShiftSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi smena qo'shish")
    def post(self, request):
        serializer = ShiftSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Shifts"])
class HallShiftListCreateAPIView(ShiftListCreateAPIView):
    """Compatibility route for ``/halls/<hall_id>/shifts/``."""

    @extend_schema(operation_id="hall_shift_list", summary="Zal smenalalari ro'yxati")
    def get(self, request, hall_id):
        get_object_or_404(WeddingHall.objects.only("id"), pk=hall_id)
        queryset = Shift.objects.filter(hall_id=hall_id)
        serializer = ShiftSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(operation_id="hall_shift_create", summary="Zalga yangi smena qo'shish")
    def post(self, request, hall_id):
        get_object_or_404(WeddingHall.objects.only("id"), pk=hall_id)
        data = request.data.copy()
        data["hall"] = hall_id
        serializer = ShiftSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Shifts"])
class ShiftDetailAPIView(APIView):
    """
    GET    — Smena tafsilotlarini olish.
    PUT    — Smena ma'lumotlarini to'liq yangilash.
    PATCH  — Smena ma'lumotlarini qisman yangilash.
    DELETE — Smenani o'chirish.
    """
    serializer_class = ShiftSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_object(self, pk):
        obj = get_object_or_404(Shift, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="shift_detail", summary="Smena tafsilotlarini olish")
    def get(self, request, pk):
        shift = self.get_object(pk)
        serializer = ShiftSerializer(shift, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Smena ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        shift = self.get_object(pk)
        serializer = ShiftSerializer(shift, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Smena ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        shift = self.get_object(pk)
        serializer = ShiftSerializer(shift, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Smenani o'chirish")
    def delete(self, request, pk):
        shift = self.get_object(pk)
        shift.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# Package Views
# =====================================================================

@extend_schema(tags=["Packages"])
class PackageListCreateAPIView(APIView):
    """
    GET  — Paketlar ro'yxati (?hall=<id> filter mavjud).
    POST — Yangi paket qo'shish.
    """
    serializer_class = PackageSerializer
    permission_classes = [IsOwnerOrReadOnly]

    @extend_schema(operation_id="package_list", summary="Paketlar ro'yxatini olish (hall bo'yicha filter)")
    def get(self, request):
        queryset = Package.objects.all()
        hall_id = request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        serializer = PackageSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi paket qo'shish")
    def post(self, request):
        serializer = PackageSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Packages"])
class PackageDetailAPIView(APIView):
    """
    GET    — Paket tafsilotlarini olish.
    PUT    — Paket ma'lumotlarini to'liq yangilash.
    PATCH  — Paket ma'lumotlarini qisman yangilash.
    DELETE — Paketni o'chirish.
    """
    serializer_class = PackageSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_object(self, pk):
        obj = get_object_or_404(Package, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="package_detail", summary="Paket tafsilotlarini olish")
    def get(self, request, pk):
        package = self.get_object(pk)
        serializer = PackageSerializer(package, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Paket ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        package = self.get_object(pk)
        serializer = PackageSerializer(package, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Paket ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        package = self.get_object(pk)
        serializer = PackageSerializer(package, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Paketni o'chirish")
    def delete(self, request, pk):
        package = self.get_object(pk)
        package.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# Decoration Views
# =====================================================================

@extend_schema(tags=["Decorations"])
class DecorationListCreateAPIView(APIView):
    """
    GET  — Dekoratsiyalar ro'yxati (?hall=<id> filter mavjud).
    POST — Yangi dekoratsiya qo'shish.
    """
    serializer_class = DecorationSerializer
    permission_classes = [IsOwnerOrReadOnly]

    @extend_schema(operation_id="decoration_list", summary="Dekoratsiyalar ro'yxatini olish (hall bo'yicha filter)")
    def get(self, request):
        queryset = Decoration.objects.all()
        hall_id = request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        serializer = DecorationSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi dekoratsiya qo'shish")
    def post(self, request):
        serializer = DecorationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Decorations"])
class DecorationDetailAPIView(APIView):
    """
    GET    — Dekoratsiya tafsilotlarini olish.
    PUT    — Dekoratsiya ma'lumotlarini to'liq yangilash.
    PATCH  — Dekoratsiya ma'lumotlarini qisman yangilash.
    DELETE — Dekoratsiyani o'chirish.
    """
    serializer_class = DecorationSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_object(self, pk):
        obj = get_object_or_404(Decoration, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="decoration_detail", summary="Dekoratsiya tafsilotlarini olish")
    def get(self, request, pk):
        decoration = self.get_object(pk)
        serializer = DecorationSerializer(decoration, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Dekoratsiya ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        decoration = self.get_object(pk)
        serializer = DecorationSerializer(decoration, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Dekoratsiya ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        decoration = self.get_object(pk)
        serializer = DecorationSerializer(decoration, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Dekoratsiyani o'chirish")
    def delete(self, request, pk):
        decoration = self.get_object(pk)
        decoration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =====================================================================
# ShiftBlock Views
# =====================================================================

@extend_schema(tags=["Shift Blocks"])
class ShiftBlockListCreateAPIView(APIView):
    """
    GET  — Bloklangan smenalar ro'yxati (?hall=<id> filter mavjud).
    POST — Yangi smena bloki qo'shish.
    """
    serializer_class = ShiftBlockSerializer
    permission_classes = [IsOwnerOrReadOnly]

    @extend_schema(operation_id="shift_block_list", summary="Bloklangan smenalar ro'yxatini olish (hall bo'yicha filter)")
    def get(self, request):
        queryset = ShiftBlock.objects.all()
        hall_id = request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        serializer = ShiftBlockSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Yangi smena bloki qo'shish")
    def post(self, request):
        serializer = ShiftBlockSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Shift Blocks"])
class ShiftBlockDetailAPIView(APIView):
    """
    GET    — Smena bloki tafsilotlarini olish.
    PUT    — Smena bloki ma'lumotlarini to'liq yangilash.
    PATCH  — Smena bloki ma'lumotlarini qisman yangilash.
    DELETE — Smena blokini o'chirish.
    """
    serializer_class = ShiftBlockSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_object(self, pk):
        obj = get_object_or_404(ShiftBlock, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(operation_id="shift_block_detail", summary="Smena bloki tafsilotlarini olish")
    def get(self, request, pk):
        block = self.get_object(pk)
        serializer = ShiftBlockSerializer(block, context={'request': request})
        return Response(serializer.data)

    @extend_schema(summary="Smena bloki ma'lumotlarini to'liq yangilash")
    def put(self, request, pk):
        block = self.get_object(pk)
        serializer = ShiftBlockSerializer(block, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Smena bloki ma'lumotlarini qisman yangilash")
    def patch(self, request, pk):
        block = self.get_object(pk)
        serializer = ShiftBlockSerializer(block, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Smena blokini o'chirish")
    def delete(self, request, pk):
        block = self.get_object(pk)
        block.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
