#!/bin/bash
# =============================================================================
# Bootstrap da EC2 (Ubuntu 24.04): cole em "Advanced details > User data" ao
# criar a instância. Roda uma única vez, como root, no primeiro boot.
#
# Monta staging e produção na MESMA instância, isolados por diretório,
# banco e .env próprios:
#   produção -> https://<ip-com-hifens>.sslip.io        (portas 80/443, HTTPS automático)
#   staging  -> http://<ip-com-hifens>.sslip.io:8080    (porta 8080, só HTTP)
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
        local site="$HOST" http_port=80 https_port=443 ssl=true hsts=3600 cookies=true
        local url="https://$HOST" workers=2
    else
        local site=":80" http_port=8080 https_port=8443 ssl=false hsts=0 cookies=false
        local url="http://$HOST:8080" workers=1
    fi

    cat > "$dir/.env" <<EOF
# Gerado pelo ec2-user-data.sh em $(date -u +%FT%TZ)
DJANGO_ENV=$ambiente
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(segredo)
DJANGO_ALLOWED_HOSTS=$HOST,$PUBLIC_IP
CSRF_TRUSTED_ORIGINS=$url
CORS_ALLOWED_ORIGINS=$url
DJANGO_SECURE_SSL_REDIRECT=$ssl
DJANGO_SECURE_HSTS_SECONDS=$hsts
DJANGO_SECURE_COOKIES=$cookies
LOG_LEVEL=INFO
GUNICORN_WORKERS=$workers

POSTGRES_DB=lacrei
POSTGRES_USER=lacrei
POSTGRES_PASSWORD=$db_pass
DATABASE_URL=postgres://lacrei:$db_pass@db:5432/lacrei

SITE_ADDRESS=$site
HTTP_PORT=$http_port
HTTPS_PORT=$https_port

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

# --- Resumo para consulta posterior: sudo cat /root/lacrei-info.txt ----------
cat > /root/lacrei-info.txt <<EOF
IP público:   $PUBLIC_IP
Produção:     https://$HOST
Staging:      http://$HOST:8080
Repositório:  https://github.com/$GITHUB_REPO
Usuário API:  admin
Senha (prod): $(grep ^DJANGO_SUPERUSER_PASSWORD= /opt/lacrei/production/.env | cut -d= -f2)
Senha (stg):  $(grep ^DJANGO_SUPERUSER_PASSWORD= /opt/lacrei/staging/.env | cut -d= -f2)
EOF
chmod 600 /root/lacrei-info.txt

echo "Bootstrap concluído."
