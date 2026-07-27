from django.urls import path
from bookings.views import (
    HallBookingListCreateAPIView,
    HallBookingDetailAPIView,
    BarBookingListCreateAPIView,
    BarBookingDetailAPIView,
    HallCalendarView,
    BarCalendarView,
)

urlpatterns = [
    # Hall Bookings
    path('hall/', HallBookingListCreateAPIView.as_view(), name='hall-booking-list'),
    path('hall/<int:pk>/', HallBookingDetailAPIView.as_view(), name='hall-booking-detail'),

    # Bar Bookings
    path('bar/', BarBookingListCreateAPIView.as_view(), name='bar-booking-list'),
    path('bar/<int:pk>/', BarBookingDetailAPIView.as_view(), name='bar-booking-detail'),

    # Calendar
    path('calendar/hall/<int:hall_id>/', HallCalendarView.as_view(), name='hall-calendar'),
    path('calendar/bar/<int:bar_id>/', BarCalendarView.as_view(), name='bar-calendar'),
]
