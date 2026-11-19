import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("consultas", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cobranca",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("asaas_payment_id", models.CharField(max_length=64, unique=True)),
                ("asaas_customer_id", models.CharField(max_length=64)),
                ("valor", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "forma_pagamento",
                    models.CharField(
                        choices=[
                            ("PIX", "Pix"),
                            ("BOLETO", "Boleto"),
                            ("CREDIT_CARD", "Cartão de crédito"),
                            ("UNDEFINED", "Escolha da pessoa pagadora"),
                        ],
                        max_length=12,
                    ),
                ),
                ("vencimento", models.DateField()),
                ("percentual_profissional", models.DecimalField(decimal_places=4, max_digits=7)),
                ("status", models.CharField(default="PENDING", max_length=40)),
                ("link_pagamento", models.URLField(blank=True, default="")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "consulta",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cobranca",
                        to="consultas.consulta",
                    ),
                ),
            ],
            options={
                "verbose_name": "cobrança",
                "verbose_name_plural": "cobranças",
                "ordering": ["-criado_em"],
            },
        ),
    ]
