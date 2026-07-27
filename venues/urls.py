from django.urls import path
from .views import (
    RegionListCreateAPIView,
    RegionDetailAPIView,
    DistrictListCreateAPIView,
    DistrictDetailAPIView,
    WeddingHallListCreateAPIView,
    WeddingHallDetailAPIView,
    BarListCreateAPIView,
    BarDetailAPIView,
    ShiftListCreateAPIView,
    ShiftDetailAPIView,
    PackageListCreateAPIView,
    PackageDetailAPIView,
    DecorationListCreateAPIView,
    DecorationDetailAPIView,
    ShiftBlockListCreateAPIView,
    ShiftBlockDetailAPIView,
)

urlpatterns = [
    # Regions
    path('regions/', RegionListCreateAPIView.as_view(), name='region-list'),
    path('regions/<int:pk>/', RegionDetailAPIView.as_view(), name='region-detail'),

    # Districts
    path('districts/', DistrictListCreateAPIView.as_view(), name='district-list'),
    path('districts/<int:pk>/', DistrictDetailAPIView.as_view(), name='district-detail'),

    # Wedding Halls
    path('halls/', WeddingHallListCreateAPIView.as_view(), name='hall-list'),
    path('halls/<int:pk>/', WeddingHallDetailAPIView.as_view(), name='hall-detail'),

    # Bars
    path('bars/', BarListCreateAPIView.as_view(), name='bar-list'),
    path('bars/<int:pk>/', BarDetailAPIView.as_view(), name='bar-detail'),

    # Shifts
    path('shifts/', ShiftListCreateAPIView.as_view(), name='shift-list'),
    path('shifts/<int:pk>/', ShiftDetailAPIView.as_view(), name='shift-detail'),

    # Packages
    path('packages/', PackageListCreateAPIView.as_view(), name='package-list'),
    path('packages/<int:pk>/', PackageDetailAPIView.as_view(), name='package-detail'),

    # Decorations
    path('decorations/', DecorationListCreateAPIView.as_view(), name='decoration-list'),
    path('decorations/<int:pk>/', DecorationDetailAPIView.as_view(), name='decoration-detail'),

    # Shift Blocks
    path('blocks/', ShiftBlockListCreateAPIView.as_view(), name='block-list'),
    path('blocks/<int:pk>/', ShiftBlockDetailAPIView.as_view(), name='block-detail'),
]
