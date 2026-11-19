"""Funções puras de sanitização de texto de entrada."""

import re
import unicodedata

from django.utils.html import strip_tags

# Caracteres de controle ASCII, exceto \t, \n e \r.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTIPLE_SPACES = re.compile(r"[ \t]+")
_NON_DIGITS = re.compile(r"\D")


def sanitize_text(value: str) -> str:
    """
    Normaliza e limpa um texto livre:

    - normaliza Unicode (NFC), evitando variações visuais do mesmo caractere;
    - remove caracteres de controle (ex.: byte nulo);
    - remove tags HTML (mitiga XSS armazenado caso algum cliente renderize o dado);
    - colapsa espaços repetidos e remove espaços nas pontas.
    """
    value = unicodedata.normalize("NFC", value)
    value = _CONTROL_CHARS.sub("", value)
    value = strip_tags(value)
    value = _MULTIPLE_SPACES.sub(" ", value)
    return value.strip()


def only_digits(value: str) -> str:
    """Mantém apenas dígitos (útil para CEP, telefone, CPF/CNPJ)."""
    return _NON_DIGITS.sub("", value)
