#!/usr/bin/env bash
# =============================================================================
# Smoke tests externos de um ambiente (rodam no GitHub Actions, pela internet).
#
# Uso: scripts/smoke-test.sh <url-base> [versão-esperada]
#   scripts/smoke-test.sh https://staging.exemplo.sslip.io sha-1a2b3c4
#
# Escreve uma tabela no resumo da execução ($GITHUB_STEP_SUMMARY) e salva o
# JSON do /health/ em smoke-health.json. Sai com erro se alguma checagem falhar.
# =============================================================================
set -uo pipefail

URL="${1:?Uso: smoke-test.sh <url-base> [versão-esperada]}"
URL="${URL%/}"
ESPERADA="${2:-}"
HOST="${URL#*://}"
HOST="${HOST%%/*}"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"
FALHAS=0
LINHAS=()

registrar() {  # registrar <ok|falha> <checagem> <detalhe>
    local icone="✅"
    if [ "$1" != ok ]; then icone="❌"; FALHAS=$((FALHAS + 1)); fi
    LINHAS+=("| ${icone} | $2 | $3 |")
    echo "[smoke] ${icone} $2 — $3"
}

codigo_http() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }

# 1. /health/ responde ok com a versão esperada (com novas tentativas enquanto sobe)
HEALTH=""
for _ in $(seq 1 20); do
    HEALTH="$(curl -fsS --max-time 10 "$URL/health/" 2>/dev/null || true)"
    STATUS="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("status",""))' "$HEALTH" 2>/dev/null || true)"
    VERSAO="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("version",""))' "$HEALTH" 2>/dev/null || true)"
    if [ "$STATUS" = ok ] && { [ -z "$ESPERADA" ] || [ "$VERSAO" = "$ESPERADA" ]; }; then
        break
    fi
    sleep 6
done
echo "${HEALTH:-{}}" > smoke-health.json
if [ "${STATUS:-}" = ok ] && { [ -z "$ESPERADA" ] || [ "$VERSAO" = "$ESPERADA" ]; }; then
    registrar ok "GET /health/" "\`${HEALTH}\`"
else
    registrar falha "GET /health/" "esperado status ok e versão ${ESPERADA:-qualquer}; recebido: \`${HEALTH:-sem resposta}\`"
fi

# 2. Certificado TLS válido (curl valida a cadeia e o nome por padrão)
if [[ "$URL" == https://* ]]; then
    EMISSOR="$(curl -sv --max-time 15 -o /dev/null "$URL/health/" 2>&1 | sed -n 's/^\*  issuer: //p' | head -1)"
    if [ "$(codigo_http "$URL/health/")" = 200 ]; then
        registrar ok "Certificado TLS" "válido para ${HOST} (${EMISSOR:-emissor não informado})"
    else
        registrar falha "Certificado TLS" "falha ao validar HTTPS em ${HOST}"
    fi

    # 3. HTTP redireciona para HTTPS
    CODIGO="$(codigo_http "http://${HOST}/health/")"
    case "$CODIGO" in
        301|302|307|308) registrar ok "HTTP → HTTPS" "http://${HOST} responde ${CODIGO}" ;;
        *) registrar falha "HTTP → HTTPS" "esperado redirecionamento; recebido ${CODIGO}" ;;
    esac
fi

# 4. Endpoints da API exigem autenticação
CODIGO="$(codigo_http "$URL/api/v1/profissionais/")"
if [ "$CODIGO" = 401 ]; then
    registrar ok "API protegida" "GET /api/v1/profissionais/ sem token → 401"
else
    registrar falha "API protegida" "esperado 401; recebido ${CODIGO}"
fi

# 5. Token com credenciais inválidas é recusado
CODIGO="$(codigo_http -X POST -H 'Content-Type: application/json' \
    -d '{"username":"smoke-test","password":"invalida"}' "$URL/api/v1/auth/token/")"
if [ "$CODIGO" = 401 ]; then
    registrar ok "Autenticação JWT" "credenciais inválidas → 401"
else
    registrar falha "Autenticação JWT" "esperado 401; recebido ${CODIGO}"
fi

# 6. Documentação OpenAPI publicada
CODIGO="$(codigo_http "$URL/api/schema/")"
if [ "$CODIGO" = 200 ]; then
    registrar ok "OpenAPI" "GET /api/schema/ → 200"
else
    registrar falha "OpenAPI" "esperado 200; recebido ${CODIGO}"
fi

# 7. Cabeçalhos de segurança
CABECALHOS="$(curl -sI --max-time 15 "$URL/api/v1/profissionais/" | tr -d '\r' | tr '[:upper:]' '[:lower:]')"
if grep -q '^x-content-type-options: nosniff' <<<"$CABECALHOS" && grep -q '^x-frame-options: deny' <<<"$CABECALHOS"; then
    registrar ok "Cabeçalhos de segurança" "nosniff e X-Frame-Options: DENY presentes"
else
    registrar falha "Cabeçalhos de segurança" "nosniff ou X-Frame-Options ausentes"
fi

{
    echo "### Smoke tests — ${URL}"
    echo
    echo "| | Checagem | Resultado |"
    echo "|---|---|---|"
    printf '%s\n' "${LINHAS[@]}"
    echo
} >> "$SUMMARY"

if [ "$FALHAS" -gt 0 ]; then
    echo "[smoke] ${FALHAS} checagem(ns) falharam"
    exit 1
fi
echo "[smoke] todas as checagens passaram"
