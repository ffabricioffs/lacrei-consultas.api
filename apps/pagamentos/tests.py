from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.consultas.models import Consulta
from apps.core.factories import (
    WALLET_ID_TESTE,
    AuthenticatedAPITestCase,
    criar_consulta,
    criar_profissional,
)
from apps.pagamentos.asaas import AsaasClient, AsaasError
from apps.pagamentos.models import Cobranca

WEBHOOK_TOKEN = "token-webhook-de-teste"


@override_settings(
    ASAAS_MOCK=True,
    ASAAS_WEBHOOK_TOKEN=WEBHOOK_TOKEN,
    ASAAS_PERCENTUAL_PROFISSIONAL=Decimal("90"),
)
class CobrancaTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.profissional = criar_profissional(asaas_wallet_id=WALLET_ID_TESTE)
        self.consulta = criar_consulta(self.profissional, valor=Decimal("200.00"))
        self.url = reverse("consulta-cobranca", args=[self.consulta.pk])

    def payload(self, **overrides):
        data = {
            "paciente_nome": "Maria Silva",
            "paciente_cpf_cnpj": "529.982.247-25",
            "paciente_email": "maria@exemplo.com",
            "forma_pagamento": "PIX",
            "vencimento": (timezone.localdate() + timedelta(days=2)).isoformat(),
        }
        data.update(overrides)
        return data

    def test_gera_cobranca_com_split(self):
        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        cobranca = Cobranca.objects.get()
        self.assertEqual(cobranca.consulta, self.consulta)
        self.assertTrue(cobranca.asaas_payment_id.startswith("pay_mock_"))
        self.assertEqual(cobranca.valor, Decimal("200.00"))
        self.assertEqual(cobranca.percentual_profissional, Decimal("90"))
        self.assertEqual(cobranca.status, "PENDING")
        self.assertTrue(response.data["link_pagamento"].startswith("https://"))

    def test_envia_split_para_carteira_do_profissional(self):
        gateway = MagicMock()
        gateway.criar_cliente.return_value = {"id": "cus_1"}
        gateway.criar_cobranca.return_value = {"id": "pay_1", "status": "PENDING"}

        with patch("apps.pagamentos.services.get_asaas_client", return_value=gateway):
            response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        kwargs = gateway.criar_cobranca.call_args.kwargs
        self.assertEqual(kwargs["split"], [{"walletId": WALLET_ID_TESTE, "percentualValue": 90.0}])
        self.assertEqual(kwargs["referencia_externa"], f"consulta:{self.consulta.pk}")
        self.assertEqual(gateway.criar_cliente.call_args.kwargs["cpf_cnpj"], "52998224725")

    def test_valor_informado_sobrepoe_valor_da_consulta(self):
        response = self.client.post(self.url, self.payload(valor="180.50"), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Cobranca.objects.get().valor, Decimal("180.50"))

    def test_consulta_sem_valor(self):
        self.consulta.valor = None
        self.consulta.save()

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valor", response.data)

    def test_profissional_sem_carteira_asaas(self):
        self.profissional.asaas_wallet_id = None
        self.profissional.save()

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profissional", response.data)

    def test_consulta_cancelada_nao_pode_ser_cobrada(self):
        self.consulta.status = Consulta.Status.CANCELADA
        self.consulta.save()

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cobranca_duplicada(self):
        self.client.post(self.url, self.payload(), format="json")

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Cobranca.objects.count(), 1)

    def test_cpf_invalido(self):
        response = self.client.post(
            self.url, self.payload(paciente_cpf_cnpj="111.111.111-11"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("paciente_cpf_cnpj", response.data)

    def test_vencimento_no_passado(self):
        ontem = (timezone.localdate() - timedelta(days=1)).isoformat()

        response = self.client.post(self.url, self.payload(vencimento=ontem), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("vencimento", response.data)

    def test_forma_de_pagamento_invalida(self):
        response = self.client.post(self.url, self.payload(forma_pagamento="CHEQUE"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consulta_inexistente(self):
        url = reverse("consulta-cobranca", args=[999999])

        response = self.client.post(url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_falha_no_asaas_retorna_502(self):
        gateway = MagicMock()
        gateway.criar_cliente.side_effect = AsaasError("fora do ar")

        with patch("apps.pagamentos.services.get_asaas_client", return_value=gateway):
            response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(Cobranca.objects.exists())

    def test_consulta_cobranca(self):
        self.client.post(self.url, self.payload(), format="json")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["consulta"], self.consulta.pk)

    def test_consulta_sem_cobranca(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nao_remove_consulta_com_cobranca(self):
        self.client.post(self.url, self.payload(), format="json")

        response = self.client.delete(reverse("consulta-detail", args=[self.consulta.pk]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(ASAAS_MOCK=True, ASAAS_WEBHOOK_TOKEN=WEBHOOK_TOKEN)
class AsaasWebhookTests(APITestCase):
    """O webhook é público (sem JWT) e autenticado pelo token do Asaas."""

    def setUp(self):
        self.url = reverse("asaas-webhook")
        consulta = criar_consulta(criar_profissional(asaas_wallet_id=WALLET_ID_TESTE))
        self.cobranca = Cobranca.objects.create(
            consulta=consulta,
            asaas_payment_id="pay_123",
            asaas_customer_id="cus_123",
            valor=Decimal("100.00"),
            forma_pagamento="PIX",
            vencimento=timezone.localdate(),
            percentual_profissional=Decimal("90"),
        )

    def evento(self, event="PAYMENT_RECEIVED", status_asaas="RECEIVED", payment_id="pay_123"):
        return {"event": event, "payment": {"id": payment_id, "status": status_asaas}}

    def test_atualiza_status_da_cobranca(self):
        response = self.client.post(
            self.url, self.evento(), format="json", HTTP_ASAAS_ACCESS_TOKEN=WEBHOOK_TOKEN
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, "RECEIVED")

    def test_token_invalido(self):
        response = self.client.post(
            self.url, self.evento(), format="json", HTTP_ASAAS_ACCESS_TOKEN="errado"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, "PENDING")

    def test_sem_token(self):
        response = self.client.post(self.url, self.evento(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ASAAS_WEBHOOK_TOKEN="")
    def test_recusa_tudo_se_token_nao_configurado(self):
        response = self.client.post(
            self.url, self.evento(), format="json", HTTP_ASAAS_ACCESS_TOKEN=""
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_evento_desconhecido_e_ignorado(self):
        response = self.client.post(
            self.url,
            self.evento(event="EVENTO_QUALQUER", status_asaas="HACKED"),
            format="json",
            HTTP_ASAAS_ACCESS_TOKEN=WEBHOOK_TOKEN,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, "PENDING")

    def test_cobranca_desconhecida_responde_200(self):
        response = self.client.post(
            self.url,
            self.evento(payment_id="pay_inexistente"),
            format="json",
            HTTP_ASAAS_ACCESS_TOKEN=WEBHOOK_TOKEN,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AsaasClientTests(SimpleTestCase):
    def setUp(self):
        self.client_asaas = AsaasClient(
            api_url="https://api-sandbox.asaas.com/v3", api_key="chave-teste", timeout=5
        )

    @patch("apps.pagamentos.asaas.requests.request")
    def test_cria_cobranca_com_payload_e_cabecalhos_corretos(self, mock_request):
        mock_request.return_value = MagicMock(status_code=200, json=lambda: {"id": "pay_1"})

        resultado = self.client_asaas.criar_cobranca(
            customer_id="cus_1",
            valor=Decimal("150.00"),
            vencimento=timezone.localdate(),
            forma_pagamento="PIX",
            descricao="Consulta",
            referencia_externa="consulta:1",
            split=[{"walletId": WALLET_ID_TESTE, "percentualValue": 90.0}],
        )

        self.assertEqual(resultado, {"id": "pay_1"})
        args, kwargs = mock_request.call_args
        self.assertEqual(args, ("POST", "https://api-sandbox.asaas.com/v3/payments"))
        self.assertEqual(kwargs["headers"]["access_token"], "chave-teste")
        self.assertEqual(kwargs["json"]["customer"], "cus_1")
        self.assertEqual(kwargs["json"]["value"], 150.0)
        self.assertEqual(kwargs["json"]["split"][0]["walletId"], WALLET_ID_TESTE)
        self.assertEqual(kwargs["timeout"], 5)

    @patch("apps.pagamentos.asaas.requests.request")
    def test_cria_cliente(self, mock_request):
        mock_request.return_value = MagicMock(status_code=200, json=lambda: {"id": "cus_1"})

        self.client_asaas.criar_cliente(nome="Maria", cpf_cnpj="52998224725")

        kwargs = mock_request.call_args.kwargs
        self.assertEqual(kwargs["json"], {"name": "Maria", "cpfCnpj": "52998224725"})

    @patch("apps.pagamentos.asaas.requests.request")
    def test_erro_http_vira_asaas_error(self, mock_request):
        mock_request.return_value = MagicMock(status_code=400)

        with self.assertRaises(AsaasError):
            self.client_asaas.criar_cliente(nome="Maria", cpf_cnpj="52998224725")

    @patch("apps.pagamentos.asaas.requests.request", side_effect=requests.Timeout())
    def test_falha_de_rede_vira_asaas_error(self, _mock_request):
        with self.assertRaises(AsaasError):
            self.client_asaas.criar_cliente(nome="Maria", cpf_cnpj="52998224725")
