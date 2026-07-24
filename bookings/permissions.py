from rest_framework import permissions

class IsBookingParticipant(permissions.BasePermission):
    """
    Custom permission to ensure only:
    1. The client who made the booking,
    2. The owner of the booked venue,
    3. Platform admins,
    can view or modify the specific booking record.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Admins or superusers bypass participant checks
        if request.user.is_superuser or request.user.role == 'ADMIN':
            return True

        # Check client ownership
        if obj.user == request.user:
            return True

        # Check venue owner ownership
        if hasattr(obj, 'hall'):
            return obj.hall.owner == request.user
        elif hasattr(obj, 'bar'):
            return obj.bar.owner == request.user

        return False
