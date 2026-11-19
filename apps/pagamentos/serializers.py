from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.core.fields import DigitsField, SanitizedCharField
from apps.core.validators import cpf_ou_cnpj_valido
from apps.pagamentos.models import Cobranca


class CriarCobrancaSerializer(serializers.Serializer):
    paciente_nome = SanitizedCharField(max_length=150, min_length=2)
    paciente_cpf_cnpj = DigitsField(allowed_lengths=(11, 14))
    paciente_email = serializers.EmailField(required=False, allow_null=True)
    forma_pagamento = serializers.ChoiceField(choices=Cobranca.FormaPagamento.choices)
    vencimento = serializers.DateField()
    valor = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )

    def validate_paciente_cpf_cnpj(self, value: str) -> str:
        if not cpf_ou_cnpj_valido(value):
            raise serializers.ValidationError("CPF/CNPJ inválido.")
        return value

    def validate_vencimento(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("O vencimento não pode estar no passado.")
        return value


class CobrancaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cobranca
        fields = [
            "id",
            "consulta",
            "asaas_payment_id",
            "valor",
            "forma_pagamento",
            "vencimento",
            "percentual_profissional",
            "status",
            "link_pagamento",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = fields
