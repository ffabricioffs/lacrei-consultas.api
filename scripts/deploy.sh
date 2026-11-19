#!/usr/bin/env bash
# =============================================================================
# Deploy de uma versão (tag de imagem) no servidor, com rollback automático.
#
# Uso (no diretório do ambiente, ex.: /opt/lacrei/staging):
#   IMAGE_NAME=ghcr.io/usuario/lacrei-consultas-api ./deploy.sh sha-1a2b3c4
#
# Variáveis opcionais:
#   SKIP_MIGRATIONS=true   não roda migrações (usado pelo rollback.sh)
#   HEALTH_RETRIES=20      tentativas do healthcheck (intervalo de 3s)
#
# Estado mantido no diretório:
#   .deployed_tag   versão atualmente no ar
#   .previous_tag   versão anterior (alvo padrão do rollback)
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

NEW_TAG="${1:?Uso: ./deploy.sh <image_tag>}"
: "${IMAGE_NAME:?Defina IMAGE_NAME (ex.: ghcr.io/usuario/lacrei-consultas-api)}"
export IMAGE_NAME
HEALTH_RETRIES="${HEALTH_RETRIES:-20}"
COMPOSE=(docker compose -f docker-compose.prod.yml)

log() { echo "[deploy $(date -u +%H:%M:%S)] $*"; }

CURRENT_TAG="$(cat .deployed_tag 2>/dev/null || true)"

healthcheck() {
    local expected_tag="$1"
    for _ in $(seq 1 "$HEALTH_RETRIES"); do
        if "${COMPOSE[@]}" exec -T web python - "$expected_tag" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health/", timeout=5) as resp:
        data = json.load(resp)
except Exception:
    sys.exit(1)
sys.exit(0 if data.get("status") == "ok" and data.get("version") == sys.argv[1] else 1)
PY
        then
            return 0
        fi
        sleep 3
    done
    return 1
}

start_version() {
    export IMAGE_TAG="$1"
    "${COMPOSE[@]}" up -d --remove-orphans web caddy
}

log "Versão atual: ${CURRENT_TAG:-nenhuma} | nova versão: ${NEW_TAG}"

export IMAGE_TAG="$NEW_TAG"
log "Baixando imagem ${IMAGE_NAME}:${NEW_TAG}"
"${COMPOSE[@]}" pull web

log "Garantindo banco de dados no ar"
"${COMPOSE[@]}" up -d --wait db

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    log "Aplicando migrações"
    "${COMPOSE[@]}" run --rm --no-deps web python manage.py migrate --noinput
fi

log "Subindo nova versão"
start_version "$NEW_TAG"

if healthcheck "$NEW_TAG"; then
    if [ -n "$CURRENT_TAG" ] && [ "$CURRENT_TAG" != "$NEW_TAG" ]; then
        echo "$CURRENT_TAG" > .previous_tag
    fi
    echo "$NEW_TAG" > .deployed_tag
    docker image prune -f --filter "until=168h" >/dev/null || true
    log "Deploy concluído com sucesso: ${NEW_TAG}"
    exit 0
fi

log "ERRO: healthcheck falhou para ${NEW_TAG}. Logs recentes:"
"${COMPOSE[@]}" logs --tail=50 web || true

if [ -n "$CURRENT_TAG" ] && [ "$CURRENT_TAG" != "$NEW_TAG" ]; then
    log "Rollback automático para ${CURRENT_TAG}"
    start_version "$CURRENT_TAG"
    if healthcheck "$CURRENT_TAG"; then
        log "Rollback concluído: ${CURRENT_TAG} está no ar."
    else
        log "ATENÇÃO: rollback também falhou. Intervenção manual necessária."
    fi
else
    log "Sem versão anterior para rollback."
fi
exit 1
