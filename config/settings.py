"""
Configurações do projeto Lacrei Consultas API.

Toda configuração sensível ou que muda por ambiente (desenvolvimento, staging,
produção) vem de variáveis de ambiente, seguindo o 12-Factor App.
Veja `.env.example` para a lista completa.
"""

import os
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "sim"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Ambiente
# ---------------------------------------------------------------------------
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development")  # development | staging | production
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
APP_VERSION = os.environ.get("APP_VERSION", "dev")

DEBUG = env_bool("DJANGO_DEBUG", default=DJANGO_ENV == "development")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DJANGO_ENV in {"staging", "production"}:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY é obrigatória em staging/produção.")
    SECRET_KEY = "dev-inseguro-nao-use-em-producao"  # noqa: S105

# localhost/127.0.0.1 ficam sempre liberados para o healthcheck interno do container.
ALLOWED_HOSTS = list(
    dict.fromkeys(env_list("DJANGO_ALLOWED_HOSTS", "localhost") + ["localhost", "127.0.0.1"])
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Aplicações
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    # Projeto
    "apps.core",
    "apps.profissionais",
    "apps.consultas",
    "apps.pagamentos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestLoggingMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Banco de dados (PostgreSQL)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default="postgres://lacrei:lacrei@localhost:5432/lacrei",
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Senhas, i18n e arquivos estáticos
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if TESTING:
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}

# Limita o tamanho do corpo das requisições (mitiga abuso/DoS).
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024  # 1 MB

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Todos os retornos e entradas em JSON.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("THROTTLE_ANON", "30/min"),
        "user": os.environ.get("THROTTLE_USER", "300/min"),
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
if TESTING:
    # Evita falsos negativos por limite de requisições durante a suíte.
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "1"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Lacrei Saúde — API de Consultas",
    "DESCRIPTION": (
        "API RESTful para gerenciamento de profissionais da saúde e consultas médicas. "
        "Autentique-se em `/api/v1/auth/token/` e envie `Authorization: Bearer <token>`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# CORS — apenas origens explicitamente autorizadas (nunca "*").
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_PREFLIGHT_MAX_AGE = 86400

# ---------------------------------------------------------------------------
# Segurança HTTP
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# O proxy reverso (Caddy) termina o TLS e repassa o protocolo original.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_FOR = env_bool("USE_X_FORWARDED_FOR", default=not DEBUG)

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", default=not DEBUG)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SESSION_COOKIE_HTTPONLY = True

# ---------------------------------------------------------------------------
# Logs (JSON no stdout — coletados pelo Docker / CloudWatch)
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
if TESTING:
    LOG_LEVEL = "CRITICAL"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.core.log_formatters.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # Logs de acesso: uma linha por requisição.
        "lacrei.access": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # Logs de erro da aplicação (exceções não tratadas, falhas externas).
        "lacrei.errors": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "lacrei.pagamentos": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Integração Asaas (pagamentos com split)
# ---------------------------------------------------------------------------
ASAAS_API_URL = os.environ.get("ASAAS_API_URL", "https://api-sandbox.asaas.com/v3")
ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY", "")
ASAAS_WEBHOOK_TOKEN = os.environ.get("ASAAS_WEBHOOK_TOKEN", "")
ASAAS_MOCK = env_bool("ASAAS_MOCK", default=True)
ASAAS_TIMEOUT_SECONDS = int(os.environ.get("ASAAS_TIMEOUT_SECONDS", "10"))
# Percentual do valor líquido repassado à pessoa profissional via split.
ASAAS_PERCENTUAL_PROFISSIONAL = Decimal(os.environ.get("ASAAS_PERCENTUAL_PROFISSIONAL", "90"))

if not ASAAS_MOCK and not ASAAS_API_KEY and DJANGO_ENV in {"staging", "production"}:
    raise ImproperlyConfigured("ASAAS_API_KEY é obrigatória quando ASAAS_MOCK=False.")
