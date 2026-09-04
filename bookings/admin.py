from django.contrib import admin

from .models import BarBooking, HallBooking


@admin.register(HallBooking)
class HallBookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hall",
        "date",
        "shift",
        "user",
        "status",
        "total_price",
        "is_deposit_paid",
        "created_at",
    )
    list_filter = ("status", "is_deposit_paid", "date")
    search_fields = ("hall__name", "user__phone_number", "user__first_name", "user__last_name")
    date_hierarchy = "date"
    list_select_related = ("hall", "shift", "user")


@admin.register(BarBooking)
class BarBookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bar",
        "date",
        "start_time",
        "end_time",
        "user",
        "status",
        "total_price",
        "is_deposit_paid",
        "created_at",
    )
    list_filter = ("status", "is_deposit_paid", "date")
    search_fields = ("bar__name", "user__phone_number", "user__first_name", "user__last_name")
    date_hierarchy = "date"
    list_select_related = ("bar", "user")
