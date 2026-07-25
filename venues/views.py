from typing import Any
from adrf.viewsets import ModelViewSet
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, extend_schema_view
from users.models import User
from .models import WeddingHall, Bar, Shift, Package, Decoration, ShiftBlock
from .serializers import (
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


class BaseVenueViewSet(ModelViewSet):
    """
    Base ViewSet for venue models (WeddingHall, Bar).
    Provides queryset filtering by ownership (`my_venues=true`) and standard perform_create/update logic.
    """
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        queryset = super().get_queryset()
        my_venues = self.request.query_params.get('my_venues')

        if _is_truthy_query_param(my_venues):
            user = self.request.user
            if user and user.is_authenticated:
                if user.is_superuser or getattr(user, 'role', None) == User.Role.ADMIN:
                    return queryset
                return queryset.filter(owner=user)
            return queryset.none()

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
    update=extend_schema(summary="To'yxona ma'lumotlarini to'liq yangilash"),
    partial_update=extend_schema(summary="To'yxona ma'lumotlarini qisman yangilash"),
    destroy=extend_schema(summary="To'yxonani o'chirish"),
)
@extend_schema(tags=["Wedding Halls"])
class WeddingHallViewSet(BaseVenueViewSet):
    """
    To'yxonalar boshqaruvi uchun API. 
    Joy egalari o'z zallarini boshqarishlari mumkin.
    `my_venues=true` parametri uzatilganda faqat joriy foydalanuvchiga tegishli to'yxonalar qaytariladi.
    """
    queryset = WeddingHall.objects.select_related('owner').prefetch_related('gallery_images').all()
    serializer_class = WeddingHallSerializer


@extend_schema_view(
    list=extend_schema(summary="Barcha barlar ro'yxatini olish (my_venues=true bo'lsa faqat o'zinikini)"),
    retrieve=extend_schema(summary="Bar tafsilotlarini olish"),
    create=extend_schema(summary="Yangi bar qo'shish (Faqat Joy egalari)"),
    update=extend_schema(summary="Bar ma'lumotlarini to'liq yangilash"),
    partial_update=extend_schema(summary="Bar ma'lumotlarini qisman yangilash"),
    destroy=extend_schema(summary="Barni o'chirish"),
)
@extend_schema(tags=["Bars"])
class BarViewSet(BaseVenueViewSet):
    """
    Soatbay ijaraga beriladigan barlar boshqaruvi uchun API.
    `my_venues=true` parametri uzatilganda faqat joriy foydalanuvchiga tegishli barlar qaytariladi.
    """
    queryset = Bar.objects.select_related('owner').prefetch_related('gallery_images').all()
    serializer_class = BarSerializer


@extend_schema_view(
    list=extend_schema(summary="Barcha smenalar ro'yxatini olish"),
    retrieve=extend_schema(summary="Smena tafsilotlarini olish"),
    create=extend_schema(summary="Yangi smena qo'shish (Faqat To'yxona egasi)"),
    update=extend_schema(summary="Smenani to'liq yangilash"),
    partial_update=extend_schema(summary="Smenani qisman yangilash"),
    destroy=extend_schema(summary="Smenani o'chirish"),
)
@extend_schema(tags=["Halls - Shifts"])
class ShiftViewSet(ModelViewSet):
    """
    To'yxona smenalari (Tushlik, Kechki va h.k.) boshqaruvi uchun API.
    """
    queryset = Shift.objects.select_related('hall').all()
    serializer_class = ShiftSerializer
    permission_classes = [IsOwnerOrReadOnly]


@extend_schema_view(
    list=extend_schema(summary="Barcha paketlar ro'yxatini olish"),
    retrieve=extend_schema(summary="Paket tafsilotlarini olish"),
    create=extend_schema(summary="Yangi paket qo'shish (Faqat To'yxona egasi)"),
    update=extend_schema(summary="Paketni to'liq yangilash"),
    partial_update=extend_schema(summary="Paketni qisman yangilash"),
    destroy=extend_schema(summary="Paketni o'chirish"),
)
@extend_schema(tags=["Halls - Packages"])
class PackageViewSet(ModelViewSet):
    """
    Mehmon soniga qarab belgilangan to'yxona paketlari boshqaruvi uchun API.
    """
    queryset = Package.objects.select_related('hall').all()
    serializer_class = PackageSerializer
    permission_classes = [IsOwnerOrReadOnly]


@extend_schema_view(
    list=extend_schema(summary="Barcha dekoratsiyalar ro'yxatini olish"),
    retrieve=extend_schema(summary="Dekoratsiya tafsilotlarini olish"),
    create=extend_schema(summary="Yangi dekoratsiya variantini qo'shish (Faqat To'yxona egasi)"),
    update=extend_schema(summary="Dekoratsiyani to'liq yangilash"),
    partial_update=extend_schema(summary="Dekoratsiyani qisman yangilash"),
    destroy=extend_schema(summary="Dekoratsiyani o'chirish"),
)
@extend_schema(tags=["Halls - Decorations"])
class DecorationViewSet(ModelViewSet):
    """
    To'yxonani bezatish (dekoratsiya) variantlari va ularning qo'shimcha narxlari uchun API.
    """
    queryset = Decoration.objects.select_related('hall').all()
    serializer_class = DecorationSerializer
    permission_classes = [IsOwnerOrReadOnly]


@extend_schema_view(
    list=extend_schema(summary="Barcha smena blokirovkalarini olish"),
    retrieve=extend_schema(summary="Blokirovka tafsilotlarini olish"),
    create=extend_schema(summary="Smenani bloklash (Faqat To'yxona egasi)"),
    update=extend_schema(summary="Blokirovka sababi yoki tafsilotlarini yangilash"),
    partial_update=extend_schema(summary="Blokirovkani qisman yangilash"),
    destroy=extend_schema(summary="Blokirovkani bekor qilish (ochish)"),
)
@extend_schema(tags=["Halls - Blocks"])
class ShiftBlockViewSet(ModelViewSet):
    """
    Admin (To'yxona egasi) tomonidan ma'lum kunlardagi smenalarni bron qilishdan yopib qo'yish (HOLD/Block) uchun API.
    """
    queryset = ShiftBlock.objects.select_related('hall', 'shift').all()
    serializer_class = ShiftBlockSerializer
    permission_classes = [IsOwnerOrReadOnly]
