"""Views utilitárias: healthcheck e respostas de erro em JSON."""

import logging

from django.conf import settings
from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

error_logger = logging.getLogger("lacrei.errors")


@require_GET
def health_check(request):
    """
    Usado pelo Docker HEALTHCHECK, pelo script de deploy e pelo smoke test do CI/CD.
    Retorna a versão (tag da imagem) para confirmar qual release está no ar.
    """
    database = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        error_logger.exception("Healthcheck: banco de dados indisponível")
        database = "indisponivel"

    healthy = database == "ok"
    return JsonResponse(
        {
            "status": "ok" if healthy else "degradado",
            "database": database,
            "version": settings.APP_VERSION,
            "environment": settings.DJANGO_ENV,
        },
        status=200 if healthy else 503,
    )


def not_found(request, exception=None):
    return JsonResponse({"detail": "Recurso não encontrado."}, status=404)


def server_error(request):
    return JsonResponse({"detail": "Erro interno do servidor."}, status=500)
