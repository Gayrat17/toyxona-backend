from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """Allow only platform admins or Django superusers."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or getattr(user, "role", None) == "ADMIN")
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Public reads; authenticated venue owners/admins may write their data."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or getattr(user, "role", None) in {"VENUE_OWNER", "ADMIN"}
            )
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return True

        owner = getattr(obj, "owner", None)
        if owner is None and hasattr(obj, "hall"):
            owner = obj.hall.owner
        return bool(
            getattr(user, "role", None) == "VENUE_OWNER"
            and owner is not None
            and owner.id == user.id
        )
