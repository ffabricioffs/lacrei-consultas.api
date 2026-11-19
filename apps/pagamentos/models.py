from django.db import models


class Cobranca(models.Model):
    """
    Cobrança gerada no Asaas para uma consulta, com split para a pessoa profissional.

    Por minimização de dados (LGPD), CPF/CNPJ da pessoa paciente NÃO é armazenado aqui:
    ele é enviado ao Asaas na criação do cliente e guardamos apenas o `asaas_customer_id`.
    """

    class FormaPagamento(models.TextChoices):
        PIX = "PIX", "Pix"
        BOLETO = "BOLETO", "Boleto"
        CARTAO = "CREDIT_CARD", "Cartão de crédito"
        INDEFINIDA = "UNDEFINED", "Escolha da pessoa pagadora"

    consulta = models.OneToOneField(
        "consultas.Consulta", on_delete=models.PROTECT, related_name="cobranca"
    )
    asaas_payment_id = models.CharField(max_length=64, unique=True)
    asaas_customer_id = models.CharField(max_length=64)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(max_length=12, choices=FormaPagamento.choices)
    vencimento = models.DateField()
    percentual_profissional = models.DecimalField(max_digits=7, decimal_places=4)
    # Status como devolvido pelo Asaas (PENDING, RECEIVED, CONFIRMED, OVERDUE, REFUNDED...).
    status = models.CharField(max_length=40, default="PENDING")
    link_pagamento = models.URLField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cobrança"
        verbose_name_plural = "cobranças"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.asaas_payment_id} ({self.status})"
