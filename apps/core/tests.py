import json
import logging
import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.factories import AuthenticatedAPITestCase
from apps.core.log_formatters import JsonFormatter
from apps.core.sanitizers import only_digits, sanitize_text
from apps.core.validators import cnpj_valido, cpf_ou_cnpj_valido, cpf_valido

ORIGEM_PERMITIDA = "https://app.lacreisaude.com.br"


class HealthCheckTests(APITestCase):
    def test_healthcheck_publico_com_banco_ok(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["database"], "ok")
        self.assertIn("version", body)

    def test_healthcheck_aceita_apenas_get(self):
        response = self.client.post(reverse("health"))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AutenticacaoJWTTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "senha-forte-de-teste-123"
        cls.user = get_user_model().objects.create_user(username="ana", password=cls.password)

    def test_obtem_token_e_acessa_recurso_protegido(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "ana", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", response.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        response = self.client.get(reverse("profissional-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_renova_token(self):
        tokens = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "ana", "password": self.password},
            format="json",
        ).data

        response = self.client.post(
            reverse("token_refresh"), {"refresh": tokens["refresh"]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_credenciais_invalidas(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "ana", "password": "errada"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_invalido(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer token.invalido.qualquer")

        response = self.client.get(reverse("profissional-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sem_token(self):
        response = self.client.get(reverse("consulta-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGEM_PERMITIDA])
class CORSTests(APITestCase):
    def preflight(self, origem):
        return self.client.options(
            reverse("profissional-list"),
            HTTP_ORIGIN=origem,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )

    def test_origem_permitida_recebe_cabecalhos_cors(self):
        response = self.preflight(ORIGEM_PERMITIDA)

        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ORIGEM_PERMITIDA)

    def test_origem_nao_permitida_nao_recebe_cabecalhos_cors(self):
        response = self.preflight("https://site-malicioso.example")

        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


class LogsEMiddlewareTests(AuthenticatedAPITestCase):
    def test_gera_request_id(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(len(response.headers["X-Request-ID"]), 32)

    def test_reaproveita_request_id_valido(self):
        response = self.client.get(reverse("health"), HTTP_X_REQUEST_ID="abc-123-def-456")

        self.assertEqual(response.headers["X-Request-ID"], "abc-123-def-456")

    def test_descarta_request_id_malicioso(self):
        response = self.client.get(reverse("health"), HTTP_X_REQUEST_ID="<script>x</script>")

        self.assertNotIn("<", response.headers["X-Request-ID"])

    def test_registra_log_de_acesso(self):
        with self.assertLogs("lacrei.access", level="INFO") as logs:
            self.client.get(reverse("profissional-list"))

        registro = logs.records[0]
        self.assertEqual(registro.status, 200)
        self.assertEqual(registro.path, "/api/v1/profissionais/")
        self.assertEqual(registro.user_id, self.user.pk)

    def test_erros_4xx_sao_logados_como_warning(self):
        with self.assertLogs("lacrei.access", level="WARNING") as logs:
            self.client.get(reverse("profissional-detail", args=[999999]))

        self.assertEqual(logs.records[0].levelno, logging.WARNING)

    def test_erro_inesperado_retorna_500_json_e_e_logado(self):
        with (
            patch(
                "apps.profissionais.views.ProfissionalViewSet.list",
                side_effect=RuntimeError("falha simulada"),
            ),
            self.assertLogs("lacrei.errors", level="ERROR") as logs,
        ):
            response = self.client.get(reverse("profissional-list"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"detail": "Erro interno do servidor."})
        self.assertNotIn("falha simulada", response.content.decode())
        self.assertIn("falha simulada", logs.output[0])

    def test_rota_inexistente_retorna_json(self):
        response = self.client.get("/rota-que-nao-existe/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"detail": "Recurso não encontrado."})

    def test_cabecalhos_de_seguranca(self):
        response = self.client.get(reverse("profissional-list"))

        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertTrue(response.headers["Content-Type"].startswith("application/json"))


class GarantirSuperusuarioTests(APITestCase):
    VARS = {"DJANGO_SUPERUSER_USERNAME": "admin", "DJANGO_SUPERUSER_PASSWORD": "senha-forte-123"}

    def test_cria_superusuario_uma_unica_vez(self):
        with patch.dict(os.environ, self.VARS):
            call_command("garantir_superusuario", stdout=StringIO())
            call_command("garantir_superusuario", stdout=StringIO())

        user = get_user_model().objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("senha-forte-123"))
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_sem_variaveis_nao_faz_nada(self):
        with patch.dict(os.environ, {"DJANGO_SUPERUSER_USERNAME": ""}):
            call_command("garantir_superusuario", stdout=StringIO())

        self.assertFalse(get_user_model().objects.exists())


class SanitizacaoEValidadoresTests(SimpleTestCase):
    def test_sanitize_text(self):
        self.assertEqual(sanitize_text("  <b>Ana</b>\x07   Souza  "), "Ana Souza")
        self.assertEqual(sanitize_text("Linha 1\nLinha 2"), "Linha 1\nLinha 2")

    def test_only_digits(self):
        self.assertEqual(only_digits("(11) 99999-0000"), "11999990000")

    def test_cpf(self):
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertTrue(cpf_valido("123.456.789-09"))
        self.assertFalse(cpf_valido("123.456.789-00"))
        self.assertFalse(cpf_valido("111.111.111-11"))
        self.assertFalse(cpf_valido("123"))

    def test_cnpj(self):
        self.assertTrue(cnpj_valido("11.222.333/0001-81"))
        self.assertFalse(cnpj_valido("11.222.333/0001-00"))
        self.assertFalse(cnpj_valido("00.000.000/0000-00"))

    def test_cpf_ou_cnpj(self):
        self.assertTrue(cpf_ou_cnpj_valido("52998224725"))
        self.assertTrue(cpf_ou_cnpj_valido("11222333000181"))
        self.assertFalse(cpf_ou_cnpj_valido("1234567"))

    def test_json_formatter(self):
        record = logging.LogRecord(
            "lacrei.access", logging.INFO, __file__, 1, "GET %s", ("/x/",), None
        )
        record.status = 200

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["message"], "GET /x/")
        self.assertEqual(payload["status"], 200)
        self.assertEqual(payload["level"], "INFO")
