from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.consultas.models import Consulta
from apps.core.fields import SanitizedCharField
from apps.profissionais.models import Profissional


class ConsultaSerializer(serializers.ModelSerializer):
    profissional = serializers.PrimaryKeyRelatedField(queryset=Profissional.objects.all())
    profissional_nome_social = serializers.CharField(
        source="profissional.nome_social", read_only=True
    )
    observacoes = SanitizedCharField(max_length=1000, allow_blank=True, required=False, default="")
    valor = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Consulta
        fields = [
            "id",
            "profissional",
            "profissional_nome_social",
            "data_hora",
            "status",
            "valor",
            "observacoes",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # A regra de horário único é validada em `validate` (considera o status).
        validators = []

    def validate_data_hora(self, value):
        alterando_data = self.instance is None or self.instance.data_hora != value
        if alterando_data and value <= timezone.now():
            raise serializers.ValidationError("A consulta deve ser agendada para uma data futura.")
        return value

    def validate(self, attrs):
        instance = self.instance
        profissional = attrs.get("profissional", getattr(instance, "profissional", None))
        data_hora = attrs.get("data_hora", getattr(instance, "data_hora", None))
        status = attrs.get("status", getattr(instance, "status", Consulta.Status.AGENDADA))

        if status != Consulta.Status.CANCELADA and profissional and data_hora:
            conflitos = Consulta.objects.filter(
                profissional=profissional, data_hora=data_hora
            ).exclude(status=Consulta.Status.CANCELADA)
            if instance is not None:
                conflitos = conflitos.exclude(pk=instance.pk)
            if conflitos.exists():
                raise serializers.ValidationError(
                    {"data_hora": ["O profissional já possui uma consulta neste horário."]}
                )
        return attrs
