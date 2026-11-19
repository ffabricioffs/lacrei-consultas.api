"""
Cria o superusuário a partir de variáveis de ambiente, de forma idempotente.

Usado pelo scripts/deploy.sh a cada deploy: se o usuário já existir, nada muda.

    DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD, DJANGO_SUPERUSER_EMAIL (opcional)
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria o superusuário definido em DJANGO_SUPERUSER_* se ele ainda não existir."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD não definidos; nada a fazer.")
            return

        user_model = get_user_model()
        if user_model.objects.filter(username=username).exists():
            self.stdout.write(f"Superusuário '{username}' já existe.")
            return

        user_model.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superusuário '{username}' criado."))
