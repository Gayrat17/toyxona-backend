from rest_framework import permissions


class IsBookingParticipant(permissions.BasePermission):
    """Allow access to a booking only to its client, venue owner, or admin."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return True

        if obj.user_id == user.id:
            return True

        venue = getattr(obj, "hall", None) or getattr(obj, "bar", None)
        return bool(venue and venue.owner_id == user.id and getattr(user, "role", None) == "VENUE_OWNER")


class IsBookingManager(IsBookingParticipant):
    """Restrict status management to venue owners and platform admins."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or getattr(user, "role", None) in {"ADMIN", "VENUE_OWNER"}
            )
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return True
        venue = getattr(obj, "hall", None) or getattr(obj, "bar", None)
        return bool(
            venue
            and venue.owner_id == user.id
            and getattr(user, "role", None) == "VENUE_OWNER"
        )
