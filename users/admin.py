from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Custom Admin interface for User model without a username field.
    """
    model = User
    
    # Fields to display in the user list view
    list_display = ('phone_number', 'first_name', 'last_name', 'role', 'is_verified', 'is_staff', 'is_active')
    
    # Filters available in the sidebar
    list_filter = ('role', 'is_verified', 'is_staff', 'is_active')
    
    # Search functionality
    search_fields = ('phone_number', 'first_name', 'last_name', 'email')
    
    # Order users by phone_number
    ordering = ('phone_number',)
    
    # Fields to edit an existing user
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Shaxsiy ma\'lumotlar (Personal Info)', {'fields': ('first_name', 'last_name', 'email')}),
        ('Rollar va Status (Roles & Verification)', {'fields': ('role', 'is_verified')}),
        ('Huquqlar (Permissions)', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Muhim sanalar (Important dates)', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Fields to display when creating a user via admin
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password', 'first_name', 'last_name', 'email', 'role', 'is_verified'),
        }),
    )
