from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HallBookingViewSet,
    BarBookingViewSet,
    HallCalendarView,
    BarCalendarView,
)

router = DefaultRouter()
router.register('hall', HallBookingViewSet, basename='hall-booking')
router.register('bar', BarBookingViewSet, basename='bar-booking')

urlpatterns = [
    path('calendar/hall/<int:hall_id>/', HallCalendarView.as_view(), name='hall-calendar'),
    path('calendar/bar/<int:bar_id>/', BarCalendarView.as_view(), name='bar-calendar'),
    path('', include(router.urls)),
]
