from rest_framework import permissions

class IsPlatformAdmin(permissions.BasePermission):
    """
    Allows access only to authenticated users with 'ADMIN' role or superusers.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (getattr(request.user, 'role', None) == 'ADMIN' or request.user.is_superuser)
        )
