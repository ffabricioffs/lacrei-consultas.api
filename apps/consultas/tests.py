from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status

from apps.consultas.models import Consulta
from apps.core.factories import (
    AuthenticatedAPITestCase,
    criar_consulta,
    criar_profissional,
    data_futura,
)


class ConsultaBaseTestCase(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.profissional = criar_profissional()
        self.outro_profissional = criar_profissional(
            nome_social="Dr. Bruno Lima", email="bruno@exemplo.com"
        )
        self.url = reverse("consulta-list")

    def detail_url(self, pk):
        return reverse("consulta-detail", args=[pk])

    def payload(self, **overrides):
        data = {
            "profissional": self.profissional.pk,
            "data_hora": data_futura().isoformat(),
            "valor": "150.00",
            "observacoes": "Primeira consulta",
        }
        data.update(overrides)
        return data


class ConsultaCRUDTests(ConsultaBaseTestCase):
    def test_cria_consulta(self):
        data_hora = data_futura()

        response = self.client.post(
            self.url, self.payload(data_hora=data_hora.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        consulta = Consulta.objects.get()
        self.assertEqual(consulta.profissional, self.profissional)
        self.assertEqual(consulta.data_hora, data_hora)
        self.assertEqual(consulta.status, Consulta.Status.AGENDADA)
        self.assertEqual(response.data["profissional_nome_social"], "Dra. Alex Souza")
        self.assertEqual(response.data["valor"], "150.00")

    def test_lista_consultas(self):
        criar_consulta(self.profissional)
        criar_consulta(self.outro_profissional)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_detalha_consulta(self):
        consulta = criar_consulta(self.profissional)

        response = self.client.get(self.detail_url(consulta.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profissional"], self.profissional.pk)
        self.assertEqual(parse_datetime(response.data["data_hora"]), consulta.data_hora)

    def test_atualiza_consulta_put(self):
        consulta = criar_consulta(self.profissional)
        nova_data = data_futura(dias=10)

        response = self.client.put(
            self.detail_url(consulta.pk),
            self.payload(
                profissional=self.outro_profissional.pk,
                data_hora=nova_data.isoformat(),
                observacoes="Remarcada",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        consulta.refresh_from_db()
        self.assertEqual(consulta.profissional, self.outro_profissional)
        self.assertEqual(consulta.data_hora, nova_data)
        self.assertEqual(consulta.observacoes, "Remarcada")

    def test_atualiza_status_patch(self):
        consulta = criar_consulta(self.profissional)

        response = self.client.patch(
            self.detail_url(consulta.pk), {"status": "realizada"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        consulta.refresh_from_db()
        self.assertEqual(consulta.status, Consulta.Status.REALIZADA)

    def test_edita_consulta_passada_sem_alterar_data(self):
        passada = timezone.now() - timedelta(days=1)
        consulta = criar_consulta(self.profissional, data_hora=passada)

        response = self.client.patch(
            self.detail_url(consulta.pk), {"observacoes": "Retorno em 30 dias"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_remove_consulta(self):
        consulta = criar_consulta(self.profissional)

        response = self.client.delete(self.detail_url(consulta.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Consulta.objects.exists())

    def test_horario_de_consulta_cancelada_pode_ser_reutilizado(self):
        data_hora = data_futura()
        criar_consulta(self.profissional, data_hora=data_hora, status=Consulta.Status.CANCELADA)

        response = self.client.post(
            self.url, self.payload(data_hora=data_hora.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)


class ConsultaErrosTests(ConsultaBaseTestCase):
    def test_dados_ausentes(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profissional", response.data)
        self.assertIn("data_hora", response.data)

    def test_profissional_inexistente(self):
        response = self.client.post(self.url, self.payload(profissional=999999), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profissional", response.data)

    def test_data_no_passado(self):
        passada = timezone.now() - timedelta(hours=1)

        response = self.client.post(
            self.url, self.payload(data_hora=passada.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("data_hora", response.data)

    def test_data_em_formato_invalido(self):
        response = self.client.post(self.url, self.payload(data_hora="amanhã"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("data_hora", response.data)

    def test_horario_ocupado(self):
        data_hora = data_futura()
        criar_consulta(self.profissional, data_hora=data_hora)

        response = self.client.post(
            self.url, self.payload(data_hora=data_hora.isoformat()), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("data_hora", response.data)

    def test_status_invalido(self):
        response = self.client.post(self.url, self.payload(status="perdida"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_valor_negativo(self):
        response = self.client.post(self.url, self.payload(valor="-10.00"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valor", response.data)

    def test_consulta_inexistente(self):
        response = self.client.get(self.detail_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requisicao_sem_autenticacao(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Consulta.objects.exists())

    def test_observacoes_sanitizadas(self):
        response = self.client.post(
            self.url,
            self.payload(observacoes="<img src=x onerror=alert(1)>Trazer exames"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Consulta.objects.get().observacoes, "Trazer exames")


class BuscaConsultasPorProfissionalTests(ConsultaBaseTestCase):
    def setUp(self):
        super().setUp()
        self.consulta_1 = criar_consulta(self.profissional, data_hora=data_futura(dias=1))
        self.consulta_2 = criar_consulta(self.profissional, data_hora=data_futura(dias=2))
        self.consulta_outro = criar_consulta(self.outro_profissional)

    def test_filtra_por_profissional_id(self):
        response = self.client.get(self.url, {"profissional_id": self.profissional.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.consulta_1.pk, self.consulta_2.pk])

    def test_rota_aninhada_de_consultas_do_profissional(self):
        url = reverse("profissional-consultas", args=[self.outro_profissional.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.consulta_outro.pk)

    def test_rota_aninhada_com_profissional_inexistente(self):
        response = self.client.get(reverse("profissional-consultas", args=[999999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filtra_por_status(self):
        self.consulta_2.status = Consulta.Status.CANCELADA
        self.consulta_2.save()

        response = self.client.get(
            self.url, {"profissional_id": self.profissional.pk, "status": "cancelada"}
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.consulta_2.pk)

    def test_profissional_id_nao_numerico(self):
        response = self.client.get(self.url, {"profissional_id": "abc"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profissional_id", response.data)

    def test_sql_injection_no_profissional_id(self):
        response = self.client.get(self.url, {"profissional_id": "1 OR 1=1"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Consulta.objects.count(), 3)

    def test_status_de_filtro_invalido(self):
        response = self.client.get(self.url, {"status": "'; DROP TABLE x; --"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
