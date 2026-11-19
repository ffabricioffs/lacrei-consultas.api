import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Profissional",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("nome_social", models.CharField(max_length=150, verbose_name="nome social")),
                ("profissao", models.CharField(max_length=100, verbose_name="profissão")),
                ("cep", models.CharField(max_length=8, verbose_name="CEP")),
                ("logradouro", models.CharField(max_length=150)),
                ("numero", models.CharField(max_length=20, verbose_name="número")),
                ("complemento", models.CharField(blank=True, default="", max_length=100)),
                ("bairro", models.CharField(max_length=100)),
                ("cidade", models.CharField(max_length=100)),
                ("uf", models.CharField(max_length=2, verbose_name="UF")),
                ("email", models.EmailField(max_length=254, verbose_name="e-mail")),
                (
                    "telefone",
                    models.CharField(help_text="DDD + número, apenas dígitos.", max_length=11),
                ),
                (
                    "asaas_wallet_id",
                    models.UUIDField(blank=True, null=True, verbose_name="wallet ID Asaas"),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "profissional",
                "verbose_name_plural": "profissionais",
                "ordering": ["nome_social", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("email"),
                        name="profissional_email_unico_ci",
                    )
                ],
            },
        ),
    ]
