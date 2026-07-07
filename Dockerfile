FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY smarthr360_jwt_auth-1.1.1-py3-none-any.whl .
COPY smarthr360_integration-0.1.0-py3-none-any.whl .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN SECRET_KEY=build python manage.py collectstatic --noinput --settings=config.settings.local || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fs http://localhost:8000/healthz/ || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
