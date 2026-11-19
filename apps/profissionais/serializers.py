from rest_framework import serializers

from apps.core.fields import DigitsField, SanitizedCharField
from apps.profissionais.models import Profissional

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip


class EnderecoSerializer(serializers.Serializer):
    cep = DigitsField(allowed_lengths=(8,))
    logradouro = SanitizedCharField(max_length=150)
    numero = SanitizedCharField(max_length=20)
    complemento = SanitizedCharField(max_length=100, allow_blank=True, default="")
    bairro = SanitizedCharField(max_length=100)
    cidade = SanitizedCharField(max_length=100)
    uf = SanitizedCharField(max_length=2, min_length=2)

    def validate_uf(self, value: str) -> str:
        value = value.upper()
        if value not in UFS:
            raise serializers.ValidationError("UF inválida.")
        return value


class ContatoSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    telefone = DigitsField(allowed_lengths=(10, 11))

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class ProfissionalSerializer(serializers.ModelSerializer):
    """
    Expõe endereço e contato como objetos aninhados, mas persiste em colunas
    simples do modelo (`source="*"` achata os dados validados).
    """

    nome_social = SanitizedCharField(max_length=150, min_length=2)
    profissao = SanitizedCharField(max_length=100, min_length=2)
    endereco = EnderecoSerializer(source="*")
    contato = ContatoSerializer(source="*")

    class Meta:
        model = Profissional
        fields = [
            "id",
            "nome_social",
            "profissao",
            "endereco",
            "contato",
            "asaas_wallet_id",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate(self, attrs):
        email = attrs.get("email")
        if email:
            duplicados = Profissional.objects.filter(email__iexact=email)
            if self.instance is not None:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                raise serializers.ValidationError(
                    {"contato": {"email": ["Já existe profissional com este e-mail."]}}
                )
        return attrs
