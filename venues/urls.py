from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WeddingHallViewSet,
    BarViewSet,
    ShiftViewSet,
    PackageViewSet,
    DecorationViewSet,
    ShiftBlockViewSet,
)

# Using DefaultRouter to register API endpoints
router = DefaultRouter()
router.register('halls', WeddingHallViewSet, basename='hall')
router.register('bars', BarViewSet, basename='bar')
router.register('shifts', ShiftViewSet, basename='shift')
router.register('packages', PackageViewSet, basename='package')
router.register('decorations', DecorationViewSet, basename='decoration')
router.register('blocks', ShiftBlockViewSet, basename='block')

urlpatterns = [
    path('', include(router.urls)),
]
