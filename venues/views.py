from typing import Any
from adrf.viewsets import ModelViewSet
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAdminUser
from drf_spectacular.utils import extend_schema, extend_schema_view
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
from .permissions import IsOwnerOrReadOnly


def _is_truthy_query_param(value: Any) -> bool:
    """Helper to check if query parameter string represents truthy value."""
    if not value:
        return False
    return str(value).strip().lower() in {'true', '1', 'yes'}


class RegionViewSet(ModelViewSet):
    """
    ViewSet for listing and retrieving Regions (Viloyatlar) with nested districts.
    """
    queryset = Region.objects.prefetch_related('districts').all()
    serializer_class = RegionSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminUser()]


class DistrictViewSet(ModelViewSet):
    """
    ViewSet for listing and retrieving Districts (Tumanlar).
    Supports filtering by region via query parameter `?region=<id>`.
    """
    queryset = District.objects.select_related('region').all()
    serializer_class = DistrictSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = super().get_queryset()
        region_id = self.request.query_params.get('region')
        if region_id:
            queryset = queryset.filter(region_id=region_id)
        return queryset


class BaseVenueViewSet(ModelViewSet):
    """
    Base ViewSet for venue models (WeddingHall, Bar).
    Provides queryset filtering by ownership (`my_venues=true`) and standard perform_create/update logic.
    """
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        my_venues = params.get('my_venues')

        if _is_truthy_query_param(my_venues):
            user = self.request.user
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
                queryset = queryset.filter(region_id=int(region_param))
            else:
                from django.db.models import Q
                queryset = queryset.filter(
                    Q(region__name__icontains=region_param) | Q(address__icontains=region_param)
                )

        # 2. Filter by district (ID or Name)
        district_param = params.get('district')
        if district_param:
            if str(district_param).isdigit():
                queryset = queryset.filter(district_id=int(district_param))
            else:
                from django.db.models import Q
                queryset = queryset.filter(
                    Q(district__name__icontains=district_param) | Q(address__icontains=district_param)
                )

        # 3. Filter by search text (name or address)
        search_param = params.get('search') or params.get('q')
        if search_param:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search_param) | Q(address__icontains=search_param)
            )

        # 4. Filter by minimum capacity
        min_capacity = params.get('min_capacity')
        if min_capacity and str(min_capacity).isdigit():
            min_cap_int = int(min_capacity)
            model_class = self.serializer_class.Meta.model
            if hasattr(model_class, 'max_capacity'):
                queryset = queryset.filter(max_capacity__gte=min_cap_int)
            elif hasattr(model_class, 'capacity'):
                queryset = queryset.filter(capacity__gte=min_cap_int)

        return queryset

    def perform_create(self, serializer: Any) -> None:
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer: Any) -> None:
        if getattr(serializer.instance, 'owner', None) is None:
            serializer.save(owner=self.request.user)
        else:
            serializer.save()


@extend_schema_view(
    list=extend_schema(summary="Barcha to'yxonalar ro'yxatini olish (my_venues=true bo'lsa faqat o'zinikini)"),
    retrieve=extend_schema(summary="To'yxona tafsilotlarini olish"),
    create=extend_schema(summary="Yangi to'yxona qo'shish (Faqat Joy egalari)"),
    update=extend_schema(summary="To'yxona ma'lumotlarini yangilash"),
    partial_update=extend_schema(summary="To'yxona ma'lumotlarini qisman yangilash"),
    destroy=extend_schema(summary="To'yxonani o'chirish"),
)
class WeddingHallViewSet(BaseVenueViewSet):
    """
    ViewSet for managing WeddingHall instances.
    """
    queryset = WeddingHall.objects.select_related('owner', 'region', 'district').prefetch_related('gallery_images').all()
    serializer_class = WeddingHallSerializer


@extend_schema_view(
    list=extend_schema(summary="Barcha barlar ro'yxatini olish (my_venues=true bo'lsa faqat o'zinikini)"),
    retrieve=extend_schema(summary="Bar tafsilotlarini olish"),
    create=extend_schema(summary="Yangi bar qo'shish (Faqat Joy egalari)"),
    update=extend_schema(summary="Bar ma'lumotlarini yangilash"),
    partial_update=extend_schema(summary="Bar ma'lumotlarini qisman yangilash"),
    destroy=extend_schema(summary="Barnisi o'chirish"),
)
class BarViewSet(BaseVenueViewSet):
    """
    ViewSet for managing Bar instances.
    """
    queryset = Bar.objects.select_related('owner', 'region', 'district').prefetch_related('gallery_images').all()
    serializer_class = BarSerializer


class ShiftViewSet(ModelViewSet):
    """
    ViewSet for managing Shifts.
    """
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        hall_id = self.request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        return queryset


class PackageViewSet(ModelViewSet):
    """
    ViewSet for managing Packages.
    """
    queryset = Package.objects.all()
    serializer_class = PackageSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        hall_id = self.request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        return queryset


class DecorationViewSet(ModelViewSet):
    """
    ViewSet for managing Decorations.
    """
    queryset = Decoration.objects.all()
    serializer_class = DecorationSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        hall_id = self.request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        return queryset


class ShiftBlockViewSet(ModelViewSet):
    """
    ViewSet for managing ShiftBlocks.
    """
    queryset = ShiftBlock.objects.all()
    serializer_class = ShiftBlockSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        hall_id = self.request.query_params.get('hall')
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        return queryset
