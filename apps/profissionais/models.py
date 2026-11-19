from django.db import models
from django.db.models.functions import Lower


class Profissional(models.Model):
    """Pessoa profissional da saúde cadastrada na plataforma."""

    nome_social = models.CharField("nome social", max_length=150)
    profissao = models.CharField("profissão", max_length=100)

    # Endereço (armazenado normalizado: CEP só com dígitos, UF em maiúsculas)
    cep = models.CharField("CEP", max_length=8)
    logradouro = models.CharField(max_length=150)
    numero = models.CharField("número", max_length=20)
    complemento = models.CharField(max_length=100, blank=True, default="")
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    uf = models.CharField("UF", max_length=2)

    # Contato
    email = models.EmailField("e-mail", max_length=254)
    telefone = models.CharField(max_length=11, help_text="DDD + número, apenas dígitos.")

    # Carteira Asaas da pessoa profissional, usada no split de pagamento.
    asaas_wallet_id = models.UUIDField("wallet ID Asaas", null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profissional"
        verbose_name_plural = "profissionais"
        ordering = ["nome_social", "id"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="profissional_email_unico_ci"),
        ]

    def __str__(self) -> str:
        return f"{self.nome_social} ({self.profissao})"
