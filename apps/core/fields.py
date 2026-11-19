"""Campos de serializer que aplicam sanitização antes da validação."""

from rest_framework import serializers

from apps.core.sanitizers import only_digits, sanitize_text


class SanitizedCharField(serializers.CharField):
    """CharField que remove HTML, caracteres de controle e espaços redundantes."""

    def to_internal_value(self, data):
        value = sanitize_text(super().to_internal_value(data))
        if not value and not self.allow_blank:
            # Ex.: "<b></b>" vira string vazia após a sanitização.
            self.fail("blank")
        return value


class DigitsField(serializers.CharField):
    """
    Campo que aceita máscaras ("01310-100", "(11) 99999-0000") e armazena só dígitos,
    validando o comprimento permitido.
    """

    default_error_messages = {
        "invalid_length": "Informe {lengths} dígitos.",
    }

    def __init__(self, *, allowed_lengths: tuple[int, ...], **kwargs):
        self.allowed_lengths = allowed_lengths
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        digits = only_digits(super().to_internal_value(data))
        if len(digits) not in self.allowed_lengths:
            self.fail("invalid_length", lengths=" ou ".join(map(str, self.allowed_lengths)))
        return digits
