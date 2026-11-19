#!/usr/bin/env bash
# =============================================================================
# Rollback manual para uma versão anterior.
#
# Uso (no diretório do ambiente):
#   IMAGE_NAME=ghcr.io/usuario/lacrei-consultas-api ./rollback.sh            # volta para .previous_tag
#   IMAGE_NAME=ghcr.io/usuario/lacrei-consultas-api ./rollback.sh sha-9f8e7d6 # volta para uma tag específica
#
# Migrações NÃO são revertidas automaticamente (ver docs/ROLLBACK.md): o projeto
# segue o padrão expand/contract para que a versão anterior funcione com o schema novo.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

TARGET_TAG="${1:-$(cat .previous_tag 2>/dev/null || true)}"
if [ -z "$TARGET_TAG" ]; then
    echo "[rollback] Nenhuma versão anterior registrada. Informe a tag: ./rollback.sh <tag>" >&2
    exit 1
fi

echo "[rollback] Revertendo para ${TARGET_TAG}"
SKIP_MIGRATIONS=true exec ./deploy.sh "$TARGET_TAG"
