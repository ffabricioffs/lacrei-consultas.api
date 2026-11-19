"""Middleware de log de acesso com correlação por Request ID."""

import logging
import re
import time
import uuid

from django.conf import settings

access_logger = logging.getLogger("lacrei.access")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def _client_ip(request) -> str | None:
    if getattr(settings, "USE_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RequestLoggingMiddleware:
    """
    Registra uma linha de log por requisição (método, rota, status, duração,
    usuário e IP) e devolve o cabeçalho `X-Request-ID` para rastreio.

    Por privacidade (LGPD), não registra corpo da requisição nem query string.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming_id = request.headers.get("X-Request-ID", "")
        request.request_id = (
            incoming_id if _VALID_REQUEST_ID.match(incoming_id) else uuid.uuid4().hex
        )
        start = time.perf_counter()

        response = self.get_response(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response["X-Request-ID"] = request.request_id

        user = getattr(request, "user", None)
        user_id = user.pk if user is not None and user.is_authenticated else None

        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        access_logger.log(
            level,
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "ip": _client_ip(request),
                "user_agent": request.headers.get("User-Agent", "")[:200],
            },
        )
        return response
