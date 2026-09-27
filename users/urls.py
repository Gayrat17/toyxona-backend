from django.urls import path
from .views import (
    AdminUserDetailAPIView,
    AdminUserListAPIView,
    PlatformStatsAPIView,
)

urlpatterns = [
    path('stats/', PlatformStatsAPIView.as_view(), name='platform-stats'),
    path('admin/users/', AdminUserListAPIView.as_view(), name='admin-users-list'),
    path('admin/users/<int:pk>/', AdminUserDetailAPIView.as_view(), name='admin-users-detail'),
]
