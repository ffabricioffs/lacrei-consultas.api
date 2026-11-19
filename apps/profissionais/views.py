from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets
from rest_framework.decorators import action

from apps.consultas.serializers import ConsultaSerializer
from apps.profissionais.models import Profissional
from apps.profissionais.serializers import ProfissionalSerializer


@extend_schema(tags=["Profissionais"])
class ProfissionalViewSet(viewsets.ModelViewSet):
    """
    CRUD de profissionais da saúde.

    - `GET /api/v1/profissionais/?search=termo` busca por nome social ou profissão.
    - `GET /api/v1/profissionais/{id}/consultas/` lista as consultas da pessoa profissional.

    Profissionais com consultas vinculadas não podem ser removidos (409).
    """

    queryset = Profissional.objects.all()
    serializer_class = ProfissionalSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nome_social", "profissao", "cidade"]
    ordering_fields = ["nome_social", "criado_em"]

    @extend_schema(responses=ConsultaSerializer(many=True), tags=["Consultas"])
    @action(detail=True, methods=["get"])
    def consultas(self, request, pk=None):
        profissional = self.get_object()
        queryset = profissional.consultas.select_related("profissional").order_by("data_hora")
        page = self.paginate_queryset(queryset)
        serializer = ConsultaSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)
