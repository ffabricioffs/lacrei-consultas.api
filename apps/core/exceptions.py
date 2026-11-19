"""Exceções da API e handler central de erros."""

import logging

from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

error_logger = logging.getLogger("lacrei.errors")


class Conflito(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "A operação conflita com o estado atual do recurso."
    default_code = "conflict"


class ServicoExternoIndisponivel(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Serviço externo indisponível. Tente novamente mais tarde."
    default_code = "bad_gateway"


def custom_exception_handler(exc, context):
    """
    Estende o handler do DRF para:

    - converter `ProtectedError` (remoção de registro com vínculos) em 409;
    - converter `IntegrityError` (ex.: e-mail duplicado em condição de corrida) em 409;
    - nunca vazar stack trace: erros inesperados viram 500 genérico em JSON
      e são registrados com detalhes no logger `lacrei.errors`.
    """
    if isinstance(exc, ProtectedError):
        exc = Conflito("Este registro possui vínculos e não pode ser removido.")
    elif isinstance(exc, IntegrityError):
        exc = Conflito("Os dados enviados conflitam com um registro existente.")

    response = exception_handler(exc, context)
    request = context.get("request")
    view = context.get("view")
    extra = {
        "request_id": getattr(request, "request_id", None),
        "path": getattr(request, "path", None),
        "method": getattr(request, "method", None),
        "view": view.__class__.__name__ if view else None,
    }

    if response is None:
        error_logger.error("Erro não tratado na API", exc_info=exc, extra=extra)
        return Response(
            {"detail": "Erro interno do servidor."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if response.status_code >= 500:
        error_logger.error("Erro %s na API", response.status_code, exc_info=exc, extra=extra)
    return response
