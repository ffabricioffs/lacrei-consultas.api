#!/usr/bin/env bash
# =============================================================================
# Relatório de segregação entre os ambientes da mesma EC2 (Markdown).
#
# Executado pelo pipeline depois do deploy de produção; a saída vai para o
# resumo da execução no GitHub Actions. NUNCA imprime valores de segredos:
# apenas nomes de chaves, permissões e se os valores são iguais ou diferentes.
#
# Uso (em qualquer diretório de ambiente): ./segregation-report.sh
# =============================================================================
set -uo pipefail

cd "$(dirname "$0")"
BASE_DIR="$(dirname "$PWD")"
ENVS=(staging production)
SEGREDOS=(DJANGO_SECRET_KEY POSTGRES_PASSWORD DATABASE_URL DJANGO_SUPERUSER_PASSWORD ASAAS_WEBHOOK_TOKEN)

env_get() { grep -E "^$2=" "$1" 2>/dev/null | tail -1 | cut -d= -f2-; }
container() {  # container <projeto> <serviço>
    docker ps -q --filter "label=com.docker.compose.project=$1" \
                 --filter "label=com.docker.compose.service=$2" | head -1
}

echo "## Segregação entre staging e produção (mesma EC2)"
echo
echo "Gerado em $(date -u +%FT%TZ) na instância \`$(hostname)\`."
echo

echo "### 1. Containers por ambiente"
echo
echo "| Projeto | Container | Imagem | Redes | Portas publicadas no host |"
echo "|---|---|---|---|---|"
docker ps --filter "label=com.docker.compose.project" \
    --format '{{.Label "com.docker.compose.project"}}|{{.Names}}|{{.Image}}|{{.Networks}}|{{.Ports}}' \
    | sort | while IFS='|' read -r proj nome img redes portas; do
        echo "| ${proj} | ${nome} | \`${img}\` | ${redes} | ${portas:-nenhuma} |"
    done
echo

echo "### 2. Redes"
echo
echo "| Rede | Interna (sem internet) | Containers |"
echo "|---|---|---|"
for rede in staging_backend production_backend lacrei-edge; do
    if docker network inspect "$rede" >/dev/null 2>&1; then
        docker network inspect -f '{{.Name}}|{{.Internal}}|{{range .Containers}}{{.Name}} {{end}}' "$rede" \
            | while IFS='|' read -r n internal membros; do
                echo "| ${n} | ${internal} | ${membros} |"
            done
    fi
done
echo
echo "O banco de cada ambiente só participa da rede \`<ambiente>_backend\` (interna). A rede \`lacrei-edge\` contém apenas o proxy e os containers \`web\`."
echo

echo "### 3. Volumes de dados"
echo
echo "| Volume | Usado por |"
echo "|---|---|"
for env in "${ENVS[@]}"; do
    vol="${env}_pgdata"
    if docker volume inspect "$vol" >/dev/null 2>&1; then
        usado="$(docker ps --filter "volume=${vol}" --format '{{.Names}}' | tr '\n' ' ')"
        echo "| ${vol} | ${usado:-nenhum container} |"
    fi
done
echo

echo "### 4. Configuração e segredos (sem valores)"
echo
echo "| Ambiente | Arquivo | Dono | Permissão | DJANGO_ENV | Host público | Banco (host:porta/nome) |"
echo "|---|---|---|---|---|---|---|"
for env in "${ENVS[@]}"; do
    f="$BASE_DIR/$env/.env"
    [ -f "$f" ] || continue
    db_url="$(env_get "$f" DATABASE_URL)"
    db_alvo="${db_url##*@}"
    echo "| ${env} | \`${f}\` | $(stat -c %U "$f") | $(stat -c %a "$f") | $(env_get "$f" DJANGO_ENV) | $(env_get "$f" SITE_HOST) | ${db_alvo} |"
done
echo
echo "\`db:5432\` é resolvido dentro da rede interna de cada projeto, portanto aponta para bancos diferentes."
echo
echo "| Segredo | staging × production |"
echo "|---|---|"
for chave in "${SEGREDOS[@]}"; do
    a="$(env_get "$BASE_DIR/staging/.env" "$chave")"
    b="$(env_get "$BASE_DIR/production/.env" "$chave")"
    if [ -z "$a" ] || [ -z "$b" ]; then
        res="ausente em um dos ambientes"
    elif [ "$a" = "$b" ]; then
        res="⚠️ IGUAL"
    else
        res="✅ diferente"
    fi
    echo "| ${chave} | ${res} |"
done
echo

echo "### 5. Teste de isolamento de rede"
echo
echo "| Origem | Destino | Resultado |"
echo "|---|---|---|"
testar() {  # testar <projeto origem> <host destino> <porta>
    local web; web="$(container "$1" web)"
    [ -n "$web" ] || { echo "| web-$1 | $2:$3 | container não encontrado |"; return; }
    local saida
    saida="$(docker exec "$web" python -c "
import socket, sys
try:
    socket.create_connection(('$2', $3), timeout=3).close()
    print('conecta')
except OSError as exc:
    print('bloqueado (' + type(exc).__name__ + ')')
" 2>&1 | tail -1)"
    echo "| web-$1 | $2:$3 | ${saida} |"
}
for env in "${ENVS[@]}"; do
    outro=production; [ "$env" = production ] && outro=staging
    testar "$env" db 5432
    testar "$env" "${outro}-db-1" 5432
done
echo
echo "Esperado: cada \`web\` conecta no próprio \`db\` e **não** alcança o banco do outro ambiente."
