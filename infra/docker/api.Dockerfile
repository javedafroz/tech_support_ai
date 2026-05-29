FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY config ./config
COPY scripts ./scripts
COPY infra/docker/api-entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir -r requirements-dev.txt \
    && chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
