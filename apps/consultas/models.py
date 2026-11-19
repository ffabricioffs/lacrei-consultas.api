from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Consulta(models.Model):
    """Consulta médica vinculada a uma pessoa profissional da saúde."""

    class Status(models.TextChoices):
        AGENDADA = "agendada", "Agendada"
        REALIZADA = "realizada", "Realizada"
        CANCELADA = "cancelada", "Cancelada"

    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,  # histórico clínico não deve sumir em cascata
        related_name="consultas",
    )
    data_hora = models.DateTimeField("data e hora")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AGENDADA)
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Valor da consulta em reais (usado na cobrança via Asaas).",
    )
    observacoes = models.TextField("observações", blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "consulta"
        verbose_name_plural = "consultas"
        ordering = ["data_hora", "id"]
        indexes = [
            models.Index(fields=["profissional", "data_hora"], name="consulta_prof_data_idx")
        ]
        constraints = [
            # Um profissional não pode ter duas consultas ativas no mesmo horário.
            models.UniqueConstraint(
                fields=["profissional", "data_hora"],
                condition=~Q(status="cancelada"),
                name="consulta_horario_unico_por_profissional",
            ),
        ]

    def __str__(self) -> str:
        return f"Consulta #{self.pk} — {self.profissional} em {self.data_hora:%d/%m/%Y %H:%M}"
