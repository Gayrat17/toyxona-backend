import logging
from typing import Any, Optional
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: Any) -> Optional[Response]:
    """
    Standardized DRF exception handler that masks sensitive 500 server errors
    from leaking system internals (database schemas, tracebacks, credentials)
    to the client while logging the full exception for server diagnostics.
    """
    response = exception_handler(exc, context)

    if response is None:
        view = context.get("view")
        view_name = view.__class__.__name__ if view else "UnknownView"
        logger.exception("Unhandled server exception in %s: %s", view_name, exc)

        # In production (or when DEBUG=False), never expose internal error messages
        error_message = (
            "Serverda ichki xatolik yuz berdi. Iltimos, keyinroq qayta urining."
            if not settings.DEBUG
            else f"Ichki xatolik: {str(exc)}"
        )
        return Response(
            {
                "detail": error_message,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
