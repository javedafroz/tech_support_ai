FROM python:3.12-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir "mkdocs>=1.6.0" "mkdocs-material>=9.5.0"

COPY mkdocs.yml ./
COPY docs ./docs

EXPOSE 8088

CMD ["mkdocs", "serve", "-a", "0.0.0.0:8088"]
