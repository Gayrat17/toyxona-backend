from django.urls import path
from bookings.views import (
    HallBookingListCreateAPIView,
    HallBookingDetailAPIView,
    BarBookingListCreateAPIView,
    BarBookingDetailAPIView,
    HallBookingStatusAPIView,
    BarBookingStatusAPIView,
    HallCalendarView,
    BarCalendarView,
)

urlpatterns = [
    # Hall Bookings
    path('hall/', HallBookingListCreateAPIView.as_view(), name='hall-booking-list'),
    path('hall/<int:pk>/', HallBookingDetailAPIView.as_view(), name='hall-booking-detail'),
    path('hall/<int:pk>/status/', HallBookingStatusAPIView.as_view(), name='hall-booking-status'),

    # Bar Bookings
    path('bar/', BarBookingListCreateAPIView.as_view(), name='bar-booking-list'),
    path('bar/<int:pk>/', BarBookingDetailAPIView.as_view(), name='bar-booking-detail'),
    path('bar/<int:pk>/status/', BarBookingStatusAPIView.as_view(), name='bar-booking-status'),

    # Calendar
    path('calendar/hall/<int:hall_id>/', HallCalendarView.as_view(), name='hall-calendar'),
    path('calendar/bar/<int:bar_id>/', BarCalendarView.as_view(), name='bar-calendar'),
]
