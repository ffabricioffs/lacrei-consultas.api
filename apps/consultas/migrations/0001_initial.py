import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("profissionais", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Consulta",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("data_hora", models.DateTimeField(verbose_name="data e hora")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("agendada", "Agendada"),
                            ("realizada", "Realizada"),
                            ("cancelada", "Cancelada"),
                        ],
                        default="agendada",
                        max_length=10,
                    ),
                ),
                (
                    "valor",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Valor da consulta em reais (usado na cobrança via Asaas).",
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "observacoes",
                    models.TextField(blank=True, default="", verbose_name="observações"),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "profissional",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consultas",
                        to="profissionais.profissional",
                    ),
                ),
            ],
            options={
                "verbose_name": "consulta",
                "verbose_name_plural": "consultas",
                "ordering": ["data_hora", "id"],
                "indexes": [
                    models.Index(
                        fields=["profissional", "data_hora"], name="consulta_prof_data_idx"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=~models.Q(status="cancelada"),
                        fields=("profissional", "data_hora"),
                        name="consulta_horario_unico_por_profissional",
                    )
                ],
            },
        ),
    ]
