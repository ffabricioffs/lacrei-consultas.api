#!/bin/sh
set -e

# Em desenvolvimento as migrações rodam ao subir o container.
# Em staging/produção quem roda as migrações é o scripts/deploy.sh (antes da troca de versão).
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
