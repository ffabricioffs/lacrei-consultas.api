from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.consultas.models import Consulta
from apps.consultas.serializers import ConsultaSerializer

FILTROS_LISTAGEM = [
    OpenApiParameter(
        "profissional_id",
        OpenApiTypes.INT,
        description="Filtra as consultas pelo ID da pessoa profissional.",
    ),
    OpenApiParameter(
        "status",
        OpenApiTypes.STR,
        enum=Consulta.Status.values,
        description="Filtra pelo status da consulta.",
    ),
]


@extend_schema(tags=["Consultas"])
@extend_schema_view(list=extend_schema(parameters=FILTROS_LISTAGEM))
class ConsultaViewSet(viewsets.ModelViewSet):
    """
    CRUD de consultas médicas.

    Busca por profissional: `GET /api/v1/consultas/?profissional_id=<id>`.
    """

    serializer_class = ConsultaSerializer

    def get_queryset(self):
        queryset = Consulta.objects.select_related("profissional")
        if self.action != "list":
            return queryset

        params = self.request.query_params
        profissional_id = params.get("profissional_id")
        if profissional_id is not None:
            # Validação explícita: só aceitamos inteiros positivos. O valor nunca é
            # concatenado em SQL — o ORM usa consultas parametrizadas.
            if not (profissional_id.isascii() and profissional_id.isdigit()):
                raise ValidationError({"profissional_id": ["Informe um ID numérico válido."]})
            queryset = queryset.filter(profissional_id=int(profissional_id))

        status = params.get("status")
        if status is not None:
            if status not in Consulta.Status.values:
                raise ValidationError({"status": ["Status inválido."]})
            queryset = queryset.filter(status=status)

        return queryset
