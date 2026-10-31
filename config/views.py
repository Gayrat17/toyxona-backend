import logging
from django.db import connection
from django.http import JsonResponse
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE

logger = logging.getLogger(__name__)
def health_check(request):
    """Small unauthenticated liveness/readiness endpoint for deployments."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            # cursor.fetchone()
    except Exception as e:
        logger.error("Health check failed: %s", e, exc_info=True)
        return JsonResponse({"status": "unhealthy"}, status=HTTP_503_SERVICE_UNAVAILABLE)
    return JsonResponse({"status": "ok"})
