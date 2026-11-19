"""Utilitários compartilhados pelos testes."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.consultas.models import Consulta
from apps.profissionais.models import Profissional

WALLET_ID_TESTE = "0b763922-aa88-4cbe-a567-e3fe8511fa06"


def payload_profissional(**overrides) -> dict:
    data = {
        "nome_social": "Dra. Alex Souza",
        "profissao": "Médica de Família",
        "endereco": {
            "cep": "01310-100",
            "logradouro": "Avenida Paulista",
            "numero": "1000",
            "complemento": "Sala 12",
            "bairro": "Bela Vista",
            "cidade": "São Paulo",
            "uf": "SP",
        },
        "contato": {
            "email": "alex.souza@exemplo.com",
            "telefone": "(11) 99999-0000",
        },
    }
    data.update(overrides)
    return data


def criar_profissional(**overrides) -> Profissional:
    campos = {
        "nome_social": "Dra. Alex Souza",
        "profissao": "Médica de Família",
        "cep": "01310100",
        "logradouro": "Avenida Paulista",
        "numero": "1000",
        "complemento": "",
        "bairro": "Bela Vista",
        "cidade": "São Paulo",
        "uf": "SP",
        "email": "alex.souza@exemplo.com",
        "telefone": "11999990000",
    }
    campos.update(overrides)
    return Profissional.objects.create(**campos)


def data_futura(dias: int = 3, hora: int = 14):
    base = timezone.localtime() + timedelta(days=dias)
    return base.replace(hour=hora, minute=0, second=0, microsecond=0)


def criar_consulta(profissional: Profissional, **overrides) -> Consulta:
    campos = {"profissional": profissional, "data_hora": data_futura()}
    campos.update(overrides)
    return Consulta.objects.create(**campos)


class AuthenticatedAPITestCase(APITestCase):
    """APITestCase com uma pessoa usuária autenticada por padrão."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="api-tester", password="senha-forte-de-teste-123"
        )

    def setUp(self):
        self.client.force_authenticate(user=self.user)
