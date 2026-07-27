"""
URL configuration for Restoran & Bar Booking system.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin Panel
    path('admin/', admin.site.urls),

    # API Documentation (drf-spectacular)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Authentication & User Management (Djoser & SimpleJWT)
    path('api/v1/auth/', include('djoser.urls')),
    path('api/v1/auth/', include('djoser.urls.jwt')),

    # Core Application Routes
    path('api/v1/users/', include('users.urls')),
    path('api/v1/venues/', include('venues.urls')),
    path('api/v1/bookings/', include('bookings.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/bot/', include('telegram_bot.urls')),
]

# Serve Static and Media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
