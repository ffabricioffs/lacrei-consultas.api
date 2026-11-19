# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Estágio 1: resolve e instala as dependências com Poetry num virtualenv isolado
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG POETRY_VERSION=2.4.3
ARG INSTALL_DEV=false
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1

# Poetry fica fora do virtualenv da aplicação (não vai para a imagem final).
RUN pip install "poetry==${POETRY_VERSION}"
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        poetry install --no-root --no-ansi; \
    else \
        poetry install --only main --no-root --no-ansi; \
    fi

# ---------------------------------------------------------------------------
# Estágio 2: imagem final enxuta, sem Poetry nem compiladores, rodando sem root
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG APP_VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE=config.settings \
    APP_VERSION=${APP_VERSION}

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN chmod +x scripts/entrypoint.sh \
    && DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application"]
