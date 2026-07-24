from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow venue owners or platform admins
    to create/modify venues and their components, while clients have read-only access.
    """
    def has_permission(self, request, view):
        # Safe methods are allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Modifying methods require authentication and correct roles (VENUE_OWNER or ADMIN)
        return (
            request.user.is_authenticated and 
            (request.user.role in ['VENUE_OWNER', 'ADMIN'] or request.user.is_superuser)
        )

    def has_object_permission(self, request, view, obj):
        # Safe methods are allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Superuser / ADMIN role has full rights
        if request.user.is_superuser or request.user.role == 'ADMIN':
            return True

        # Check object level ownership:
        # 1. Direct ownership (WeddingHall, Bar)
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
            
        # 2. Sub-object ownership (Shift, Package, Decoration, ShiftBlock linked to WeddingHall)
        if hasattr(obj, 'hall'):
            return obj.hall.owner == request.user

        return False
