"""Subprocess worker: convert a PDF to Markdown with Docling.

Run as: python -m tech_support_knowledge._docling_worker <pdf_path> <out_json_path>

Isolated in its own process so a native crash (e.g. OpenCV SIGILL under
Docker Desktop <4.39 on Apple Silicon) or an OOM kill (SIGKILL) cannot
take down the API worker. The parent detects the non-zero/negative exit
code and raises a clean error.

OCR is disabled by default (KB_PDF_OCR_ENABLED=false) because RapidOCR's
torch models roughly double peak memory. Digitally authored handbooks do
not need OCR; enable only for scanned PDFs when the host has enough RAM.
"""

from __future__ import annotations

import json
import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version


def _docling_version() -> str:
    try:
        return pkg_version("docling")
    except PackageNotFoundError:
        return "unknown"


def _ocr_enabled() -> bool:
    return os.getenv("KB_PDF_OCR_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: _docling_worker <pdf_path> <out_json_path>", file=sys.stderr)
        return 2

    pdf_path, out_path = sys.argv[1], sys.argv[2]

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    from tech_support_knowledge.chunking import PAGE_BREAK_MARKER

    ocr_enabled = _ocr_enabled()
    opts = PdfPipelineOptions(do_ocr=ocr_enabled)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    print(
        f"[docling_worker] OCR={'on' if ocr_enabled else 'off'} converting {pdf_path}",
        file=sys.stderr,
    )
    result = converter.convert(pdf_path)

    # Preserve page boundaries so the ingest pipeline can chunk page-by-page.
    # Older docling-core builds lack `page_break_placeholder`; fall back cleanly.
    try:
        markdown = result.document.export_to_markdown(page_break_placeholder=PAGE_BREAK_MARKER)
    except TypeError:
        markdown = result.document.export_to_markdown()

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"markdown": markdown, "version": _docling_version()}, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
