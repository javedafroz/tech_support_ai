FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 \
        libxcb1 \
        libxrender1 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Docling is the locked PDF->Markdown converter for the KB ingest pipeline.
# Heavy ML deps (torch etc.). Installed first as a cache-stable layer so that
# ordinary source edits below do not trigger a full reinstall.
RUN pip install --no-cache-dir 'docling>=2.0.0'

# Pre-bake layout/table models so first PDF ingest does not download at request time.
# RapidOCR is omitted by default (KB_PDF_OCR_ENABLED=false); enable OCR separately if needed.
RUN python -c "\
from docling.utils.model_downloader import download_models; \
download_models(with_rapidocr=False, with_easyocr=False, progress=True)" \
    || true

COPY requirements-dev.txt pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY config ./config
COPY scripts ./scripts
COPY infra/docker/api-entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir -r requirements-dev.txt \
    && chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV KB_PDF_OCR_ENABLED=false
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
