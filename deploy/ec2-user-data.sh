#!/bin/bash
# =============================================================================
# Bootstrap da EC2 (Ubuntu 24.04): cole em "Advanced details > User data" ao
# criar a instância. Roda uma única vez, como root, no primeiro boot.
#
# Monta staging e produção na MESMA instância, isolados por diretório,
# projeto Docker Compose, banco, volume, rede interna e .env próprios.
# Um único proxy (Caddy, deploy/edge) atende os dois em HTTPS na porta 443:
#   produção -> https://<ip-com-hifens>.sslip.io
#   staging  -> https://staging.<ip-com-hifens>.sslip.io
#
# Os segredos (SECRET_KEY, senhas do banco e do usuário da API) são gerados
# aqui e nunca saem da instância. Log: /var/log/lacrei-bootstrap.log
# =============================================================================
set -euo pipefail  # sem -x: não registrar os segredos gerados no log
exec > /var/log/lacrei-bootstrap.log 2>&1
chmod 600 /var/log/lacrei-bootstrap.log

# Chave PÚBLICA usada pelo GitHub Actions para o deploy por SSH.
DEPLOY_PUBKEY="__DEPLOY_PUBKEY__"
GITHUB_REPO="__GITHUB_REPO__"

# --- Swap (instâncias pequenas têm pouca RAM para 2 Postgres + 2 APIs) -------
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- Docker + Compose --------------------------------------------------------
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
systemctl enable --now docker

# --- Chave de deploy ---------------------------------------------------------
install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
touch /home/ubuntu/.ssh/authorized_keys
grep -qF "$DEPLOY_PUBKEY" /home/ubuntu/.ssh/authorized_keys \
    || echo "$DEPLOY_PUBKEY" >> /home/ubuntu/.ssh/authorized_keys
chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
chmod 600 /home/ubuntu/.ssh/authorized_keys

# --- Endereço público (sslip.io resolve <a-b-c-d>.sslip.io para o IP a.b.c.d) --
IMDS_TOKEN=$(curl -sX PUT http://169.254.169.254/latest/api/token \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
    http://169.254.169.254/latest/meta-data/public-ipv4)
HOST="${PUBLIC_IP//./-}.sslip.io"

segredo() { openssl rand -hex 32; }

criar_env() {
    local ambiente="$1" dir="/opt/lacrei/$1"
    install -d -o ubuntu -g ubuntu "$dir"
    [ -f "$dir/.env" ] && return 0   # nunca sobrescreve um .env existente

    local db_pass admin_pass
    db_pass=$(segredo)
    admin_pass=$(openssl rand -base64 18 | tr -d '/+=')

    if [ "$ambiente" = "production" ]; then
        local site="$HOST" workers=2
    else
        local site="staging.$HOST" workers=1
    fi
    local url="https://$site"

    cat > "$dir/.env" <<EOF
# Gerado pelo ec2-user-data.sh em $(date -u +%FT%TZ)
DJANGO_ENV=$ambiente
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(segredo)
DJANGO_ALLOWED_HOSTS=$site
CSRF_TRUSTED_ORIGINS=$url
CORS_ALLOWED_ORIGINS=$url
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=3600
DJANGO_SECURE_COOKIES=true
LOG_LEVEL=INFO
GUNICORN_WORKERS=$workers

POSTGRES_DB=lacrei
POSTGRES_USER=lacrei
POSTGRES_PASSWORD=$db_pass
DATABASE_URL=postgres://lacrei:$db_pass@db:5432/lacrei

# Host público do ambiente (lido pelo proxy único em /opt/lacrei/edge)
SITE_HOST=$site

# Usuário da API, criado no primeiro deploy (scripts/deploy.sh)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=$admin_pass
DJANGO_SUPERUSER_EMAIL=

ASAAS_MOCK=true
ASAAS_API_URL=https://api-sandbox.asaas.com/v3
ASAAS_API_KEY=
ASAAS_WEBHOOK_TOKEN=$(segredo)
ASAAS_PERCENTUAL_PROFISSIONAL=90
EOF
    chown ubuntu:ubuntu "$dir/.env"
    chmod 600 "$dir/.env"
    echo "$url" > "$dir/.url"
}

criar_env production
criar_env staging
# Diretório do proxy único (preenchido pelo scripts/deploy.sh no primeiro deploy)
install -d -o ubuntu -g ubuntu /opt/lacrei/edge

# --- Resumo para consulta posterior: sudo cat /root/lacrei-info.txt ----------
cat > /root/lacrei-info.txt <<EOF
IP público:   $PUBLIC_IP
Produção:     https://$HOST
Staging:      https://staging.$HOST
Repositório:  https://github.com/$GITHUB_REPO
Usuário API:  admin
Senha (prod): $(grep ^DJANGO_SUPERUSER_PASSWORD= /opt/lacrei/production/.env | cut -d= -f2)
Senha (stg):  $(grep ^DJANGO_SUPERUSER_PASSWORD= /opt/lacrei/staging/.env | cut -d= -f2)
EOF
chmod 600 /root/lacrei-info.txt

echo "Bootstrap concluído."
