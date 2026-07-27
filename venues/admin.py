from django.contrib import admin
from .models import Region, District, WeddingHall, Bar, Media, Shift, Package, Decoration, ShiftBlock


class DistrictInline(admin.TabularInline):
    model = District
    extra = 1


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'order')
    search_fields = ('name',)
    ordering = ('order', 'name')
    inlines = [DistrictInline]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'order')
    list_filter = ('region',)
    search_fields = ('name', 'region__name')
    ordering = ('region', 'order', 'name')


@admin.register(WeddingHall)
class WeddingHallAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'district', 'owner', 'max_capacity', 'created_at')
    list_filter = ('region', 'district')
    search_fields = ('name', 'address', 'owner__phone_number')


@admin.register(Bar)
class BarAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'district', 'owner', 'capacity', 'price_per_hour', 'created_at')
    list_filter = ('region', 'district')
    search_fields = ('name', 'address', 'owner__phone_number')


admin.site.register(Media)
admin.site.register(Shift)
admin.site.register(Package)
admin.site.register(Decoration)
admin.site.register(ShiftBlock)
