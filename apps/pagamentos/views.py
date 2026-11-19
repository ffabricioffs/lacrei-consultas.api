import hmac

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.consultas.models import Consulta
from apps.pagamentos.models import Cobranca
from apps.pagamentos.serializers import CobrancaSerializer, CriarCobrancaSerializer
from apps.pagamentos.services import gerar_cobranca, processar_webhook


@extend_schema(tags=["Pagamentos"])
class CobrancaConsultaView(APIView):
    """Gera (POST) ou consulta (GET) a cobrança Asaas de uma consulta."""

    @extend_schema(responses=CobrancaSerializer)
    def get(self, request, consulta_id: int):
        consulta = get_object_or_404(Consulta, pk=consulta_id)
        try:
            cobranca = consulta.cobranca
        except Cobranca.DoesNotExist as exc:
            raise NotFound("Esta consulta ainda não possui cobrança.") from exc
        return Response(CobrancaSerializer(cobranca).data)

    @extend_schema(request=CriarCobrancaSerializer, responses={201: CobrancaSerializer})
    def post(self, request, consulta_id: int):
        consulta = get_object_or_404(
            Consulta.objects.select_related("profissional"), pk=consulta_id
        )
        serializer = CriarCobrancaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cobranca = gerar_cobranca(consulta, **serializer.validated_data)
        return Response(CobrancaSerializer(cobranca).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Pagamentos"],
    request=OpenApiTypes.OBJECT,
    responses=inline_serializer("WebhookResposta", {"recebido": serializers.BooleanField()}),
)
class AsaasWebhookView(APIView):
    """
    Recebe eventos de cobrança do Asaas.

    Autenticação: o Asaas envia o token configurado no painel no cabeçalho
    `asaas-access-token`. Se `ASAAS_WEBHOOK_TOKEN` não estiver definido, o endpoint
    recusa tudo (fail-closed).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def post(self, request):
        esperado = settings.ASAAS_WEBHOOK_TOKEN
        recebido = request.headers.get("asaas-access-token", "")
        if not esperado or not hmac.compare_digest(recebido.encode(), esperado.encode()):
            raise PermissionDenied("Token de webhook inválido.")

        payload = request.data if isinstance(request.data, dict) else {}
        processar_webhook(payload)
        # Sempre 200 para eventos válidos: evita que o Asaas pause a fila de webhooks.
        return Response({"recebido": True})
