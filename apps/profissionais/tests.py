from django.urls import reverse
from rest_framework import status

from apps.core.factories import (
    AuthenticatedAPITestCase,
    criar_consulta,
    criar_profissional,
    payload_profissional,
)
from apps.profissionais.models import Profissional


class ProfissionalCRUDTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("profissional-list")

    def detail_url(self, pk):
        return reverse("profissional-detail", args=[pk])

    # --- Create -------------------------------------------------------------
    def test_cria_profissional_com_dados_validos(self):
        response = self.client.post(self.url, payload_profissional(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        profissional = Profissional.objects.get()
        self.assertEqual(profissional.nome_social, "Dra. Alex Souza")
        # Máscaras são removidas e os dados ficam normalizados.
        self.assertEqual(profissional.cep, "01310100")
        self.assertEqual(profissional.telefone, "11999990000")
        self.assertEqual(response.data["endereco"]["cidade"], "São Paulo")
        self.assertEqual(response.data["contato"]["email"], "alex.souza@exemplo.com")

    def test_normaliza_email_e_uf(self):
        payload = payload_profissional()
        payload["contato"]["email"] = "Alex.Souza@EXEMPLO.com"
        payload["endereco"]["uf"] = "sp"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["contato"]["email"], "alex.souza@exemplo.com")
        self.assertEqual(response.data["endereco"]["uf"], "SP")

    # --- Read ---------------------------------------------------------------
    def test_lista_profissionais_paginado(self):
        criar_profissional()
        criar_profissional(nome_social="Dr. Bruno Lima", email="bruno@exemplo.com")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_busca_profissional_por_nome(self):
        criar_profissional()
        criar_profissional(nome_social="Dr. Bruno Lima", email="bruno@exemplo.com")

        response = self.client.get(self.url, {"search": "bruno"})

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["nome_social"], "Dr. Bruno Lima")

    def test_detalha_profissional(self):
        profissional = criar_profissional()

        response = self.client.get(self.detail_url(profissional.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], profissional.pk)
        self.assertEqual(response.data["endereco"]["cep"], "01310100")

    # --- Update -------------------------------------------------------------
    def test_atualiza_profissional_put(self):
        profissional = criar_profissional()
        payload = payload_profissional(nome_social="Dra. Alex S. Lima", profissao="Psicóloga")

        response = self.client.put(self.detail_url(profissional.pk), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        profissional.refresh_from_db()
        self.assertEqual(profissional.nome_social, "Dra. Alex S. Lima")
        self.assertEqual(profissional.profissao, "Psicóloga")

    def test_atualiza_parcialmente_endereco_patch(self):
        profissional = criar_profissional()

        response = self.client.patch(
            self.detail_url(profissional.pk),
            {"endereco": {"cidade": "Recife", "uf": "pe"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        profissional.refresh_from_db()
        self.assertEqual(profissional.cidade, "Recife")
        self.assertEqual(profissional.uf, "PE")
        self.assertEqual(profissional.logradouro, "Avenida Paulista")  # inalterado

    def test_patch_com_proprio_email_nao_acusa_duplicidade(self):
        profissional = criar_profissional()

        response = self.client.patch(
            self.detail_url(profissional.pk),
            {"contato": {"email": "ALEX.SOUZA@exemplo.com"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    # --- Delete -------------------------------------------------------------
    def test_remove_profissional(self):
        profissional = criar_profissional()

        response = self.client.delete(self.detail_url(profissional.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profissional.objects.exists())

    def test_nao_remove_profissional_com_consultas(self):
        profissional = criar_profissional()
        criar_consulta(profissional)

        response = self.client.delete(self.detail_url(profissional.pk))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Profissional.objects.filter(pk=profissional.pk).exists())


class ProfissionalErrosTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("profissional-list")

    def test_dados_ausentes(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for campo in ("nome_social", "profissao", "endereco", "contato"):
            self.assertIn(campo, response.data)

    def test_campos_aninhados_ausentes(self):
        payload = payload_profissional(endereco={"cep": "01310100"}, contato={})

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("logradouro", response.data["endereco"])
        self.assertIn("email", response.data["contato"])

    def test_email_invalido(self):
        payload = payload_profissional()
        payload["contato"]["email"] = "nao-e-email"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["contato"])

    def test_cep_invalido(self):
        payload = payload_profissional()
        payload["endereco"]["cep"] = "123"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cep", response.data["endereco"])

    def test_uf_invalida(self):
        payload = payload_profissional()
        payload["endereco"]["uf"] = "XX"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("uf", response.data["endereco"])

    def test_telefone_invalido(self):
        payload = payload_profissional()
        payload["contato"]["telefone"] = "1234"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("telefone", response.data["contato"])

    def test_email_duplicado_case_insensitive(self):
        criar_profissional(email="alex.souza@exemplo.com")
        payload = payload_profissional()
        payload["contato"]["email"] = "ALEX.SOUZA@exemplo.com"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["contato"])

    def test_tipo_invalido(self):
        response = self.client.post(
            self.url, payload_profissional(nome_social=["lista"]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nome_social", response.data)

    def test_profissional_inexistente(self):
        response = self.client.get(reverse("profissional-detail", args=[999999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_json_malformado(self):
        response = self.client.post(
            self.url, data='{"nome_social": ', content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_formato_nao_json_e_recusado(self):
        response = self.client.post(self.url, {"nome_social": "Ana"}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_requisicao_sem_autenticacao(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfissionalSegurancaTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("profissional-list")

    def test_remove_html_dos_campos_de_texto(self):
        payload = payload_profissional(nome_social="<script>alert('x')</script>Dra. Ana")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        nome = Profissional.objects.get().nome_social
        self.assertNotIn("<", nome)
        self.assertIn("Dra. Ana", nome)

    def test_remove_caracteres_de_controle(self):
        response = self.client.post(
            self.url, payload_profissional(nome_social="Ana\x00   Souza"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Profissional.objects.get().nome_social, "Ana Souza")

    def test_campo_vazio_apos_sanitizacao_e_recusado(self):
        response = self.client.post(
            self.url, payload_profissional(nome_social="<b></b>"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nome_social", response.data)

    def test_sql_injection_na_busca_e_tratada_como_texto(self):
        criar_profissional()
        ataque = "' OR 1=1; DROP TABLE profissionais_profissional; --"

        response = self.client.get(self.url, {"search": ataque})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(Profissional.objects.count(), 1)  # tabela intacta

    def test_sql_injection_no_cadastro_e_armazenada_como_texto(self):
        ataque = "Ana'); DELETE FROM profissionais_profissional; --"

        response = self.client.post(
            self.url, payload_profissional(nome_social=ataque), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Profissional.objects.get().nome_social, ataque)
