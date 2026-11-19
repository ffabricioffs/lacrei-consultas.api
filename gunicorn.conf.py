"""Configuração do Gunicorn (lida automaticamente a partir do diretório de trabalho)."""

import os

bind = "0.0.0.0:8000"  # noqa: S104 — exposto só na rede interna do Docker (atrás do Caddy)
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# Logs de acesso já são emitidos em JSON pelo RequestLoggingMiddleware.
accesslog = None
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Confia nos cabeçalhos X-Forwarded-* vindos do proxy reverso na rede do Docker.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")
