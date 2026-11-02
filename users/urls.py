from django.urls import path
from .views import (
    AdminUserDetailAPIView,
    AdminUserListAPIView,
    CompleteProfileView,
    PlatformStatsAPIView,
    TelegramAuthInitView,
    TelegramAuthStatusView,
)

urlpatterns = [
    path('stats/', PlatformStatsAPIView.as_view(), name='platform-stats'),
    path('admin/users/', AdminUserListAPIView.as_view(), name='admin-users-list'),
    path('admin/users/<int:pk>/', AdminUserDetailAPIView.as_view(), name='admin-users-detail'),
    path('auth/telegram/init/', TelegramAuthInitView.as_view(), name='telegram-auth-init'),
    path('auth/telegram/status/<str:session_id>/', TelegramAuthStatusView.as_view(), name='telegram-auth-status'),
    path('auth/complete-profile/', CompleteProfileView.as_view(), name='complete-profile'),
]
