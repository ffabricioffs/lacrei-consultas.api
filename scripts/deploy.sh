#!/usr/bin/env bash
# =============================================================================
# Deploy de uma versão (tag de imagem) em UM ambiente, com rollback automático.
#
# Uso (no diretório do ambiente, ex.: /opt/lacrei/staging):
#   IMAGE_NAME=ghcr.io/usuario/repo APP_URL=https://host ./deploy.sh sha-1a2b3c4
#
# O nome do diretório define o ambiente (APP_ENV): /opt/lacrei/staging -> staging.
#
# Variáveis opcionais:
#   APP_URL=https://host   URL pública do ambiente (vem do GitHub Environment).
#                          Atualiza no .env apenas configurações NÃO sensíveis
#                          (host, ALLOWED_HOSTS, CSRF, HTTPS). Segredos nunca
#                          saem do .env do servidor.
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
: "${IMAGE_NAME:?Defina IMAGE_NAME (ex.: ghcr.io/usuario/repo)}"
export IMAGE_NAME
APP_ENV="${APP_ENV:-$(basename "$PWD")}"
export APP_ENV
HEALTH_RETRIES="${HEALTH_RETRIES:-20}"
BASE_DIR="$(dirname "$PWD")"
EDGE_DIR="${EDGE_DIR:-$BASE_DIR/edge}"
EDGE_NETWORK="lacrei-edge"
COMPOSE=(docker compose -f docker-compose.prod.yml)
EDGE_COMPOSE=(docker compose --project-directory "$EDGE_DIR" -f "$EDGE_DIR/docker-compose.yml")

log() { echo "[deploy:${APP_ENV} $(date -u +%H:%M:%S)] $*"; }

# --- Utilitários de .env (somente chaves não sensíveis) -----------------------
env_get() {  # env_get <arquivo> <CHAVE>
    grep -E "^$2=" "$1" 2>/dev/null | tail -1 | cut -d= -f2- || true
}

env_set() {  # env_set <arquivo> <CHAVE> <valor>
    local file="$1" key="$2" value="$3"
    if grep -qE "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

configurar_host_publico() {
    [ -n "${APP_URL:-}" ] || return 0
    local host="${APP_URL#*://}"
    host="${host%%/*}"
    host="${host%%:*}"
    log "Host público: ${host}"
    env_set .env SITE_HOST "$host"
    env_set .env DJANGO_ALLOWED_HOSTS "$host"
    env_set .env CSRF_TRUSTED_ORIGINS "https://$host"
    env_set .env DJANGO_SECURE_SSL_REDIRECT true
    env_set .env DJANGO_SECURE_COOKIES true
}

# --- Proxy único (deploy/edge) -------------------------------------------------
host_do_ambiente() {  # host público de um diretório de ambiente
    local dir="$1" host
    host="$(env_get "$dir/.env" SITE_HOST)"
    if [ -z "$host" ]; then
        # Compatibilidade com a estrutura anterior (Caddy por ambiente).
        host="$(env_get "$dir/.env" SITE_ADDRESS)"
        case "$host" in :*|"") host="" ;; esac
    fi
    echo "$host"
}

ambientes() {  # diretórios irmãos que são ambientes (têm compose e .env)
    for dir in "$BASE_DIR"/*/; do
        dir="${dir%/}"
        if [ -f "$dir/docker-compose.prod.yml" ] && [ -f "$dir/.env" ]; then
            basename "$dir"
        fi
    done
    return 0
}

garantir_rede_edge() {
    docker network inspect "$EDGE_NETWORK" >/dev/null 2>&1 \
        || docker network create "$EDGE_NETWORK" >/dev/null
}

atualizar_proxy() {
    install -d "$EDGE_DIR"
    cp edge/docker-compose.yml edge/Caddyfile "$EDGE_DIR/"

    # Hosts de todos os ambientes da máquina (apenas hostnames, nada sensível).
    local novo="$EDGE_DIR/.env.novo" nome host
    echo "# Gerado por scripts/deploy.sh em $(date -u +%FT%TZ)" > "$novo"
    for nome in $(ambientes); do
        host="$(host_do_ambiente "$BASE_DIR/$nome")"
        [ -n "$host" ] && echo "${nome^^}_HOST=${host}" >> "$novo"
    done

    # Migração da estrutura anterior: remove o Caddy de cada ambiente e liga os
    # containers web já em execução à rede do proxy (sem derrubar o outro ambiente).
    for nome in $(ambientes); do
        local ids
        ids="$(docker ps -aq --filter "label=com.docker.compose.project=${nome}" \
                             --filter "label=com.docker.compose.service=caddy")"
        if [ -n "$ids" ]; then
            log "Removendo proxy antigo do ambiente ${nome}"
            # shellcheck disable=SC2086
            docker rm -f $ids >/dev/null
        fi
        for id in $(docker ps -q --filter "label=com.docker.compose.project=${nome}" \
                                 --filter "label=com.docker.compose.service=web"); do
            if ! docker inspect -f '{{json .NetworkSettings.Networks}}' "$id" | grep -q "\"${EDGE_NETWORK}\""; then
                docker network connect --alias "web-${nome}" "$EDGE_NETWORK" "$id"
            fi
        done
    done

    if cmp -s "$novo" "$EDGE_DIR/.env" 2>/dev/null; then
        rm -f "$novo"
        "${EDGE_COMPOSE[@]}" up -d
    else
        mv "$novo" "$EDGE_DIR/.env"
        log "Hosts do proxy atualizados"
        "${EDGE_COMPOSE[@]}" up -d --force-recreate
    fi
    "${EDGE_COMPOSE[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true
}

# --- Deploy ---------------------------------------------------------------------
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
    "${COMPOSE[@]}" up -d --remove-orphans web
}

log "Versão atual: ${CURRENT_TAG:-nenhuma} | nova versão: ${NEW_TAG}"

configurar_host_publico
garantir_rede_edge

export IMAGE_TAG="$NEW_TAG"
log "Baixando imagem ${IMAGE_NAME}:${NEW_TAG}"
"${COMPOSE[@]}" pull web

log "Garantindo banco de dados no ar"
"${COMPOSE[@]}" up -d --wait db

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    log "Aplicando migrações"
    "${COMPOSE[@]}" run --rm --no-deps web python manage.py migrate --noinput
    # Idempotente: cria o usuário da API definido em DJANGO_SUPERUSER_* só na primeira vez.
    "${COMPOSE[@]}" run --rm --no-deps web python manage.py garantir_superusuario
fi

log "Subindo nova versão"
start_version "$NEW_TAG"
atualizar_proxy

if healthcheck "$NEW_TAG"; then
    if [ -n "$CURRENT_TAG" ] && [ "$CURRENT_TAG" != "$NEW_TAG" ]; then
        echo "$CURRENT_TAG" > .previous_tag
    fi
    echo "$NEW_TAG" > .deployed_tag
    docker image prune -f --filter "until=168h" >/dev/null || true
    log "Deploy concluído com sucesso: ${NEW_TAG}"
    exit 0
fi

log "ERRO: healthcheck falhou para ${NEW_TAG}. Erros recentes (sem logs de acesso, ver docs/LOGS.md):"
"${COMPOSE[@]}" logs --no-log-prefix --tail=300 web 2>/dev/null \
    | grep -v '"logger": "lacrei.access"' | tail -40 || true

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
