"""PDF → Markdown conversion. Docling is the locked production converter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConversionResult:
    markdown: str
    converter_name: str
    converter_version: str


class PdfToMarkdownConverter(Protocol):
    def convert(self, pdf_bytes: bytes, *, filename: str = "document.pdf") -> ConversionResult: ...


class DoclingConverter:
    """Wraps IBM Docling (optional: tech-support-knowledge[docling]).

    The actual conversion runs in an isolated subprocess so that a native
    crash in Docling's dependencies (e.g. OpenCV SIGILL under Docker Desktop
    <4.39 on Apple Silicon) is reported as a clean error instead of killing
    the calling process.
    """

    def convert(self, pdf_bytes: bytes, *, filename: str = "document.pdf") -> ConversionResult:
        try:
            import docling  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install with: "
                "pip install 'tech-support-knowledge[docling]' "
                "or uv sync --extra docling"
            ) from exc

        import json
        import signal
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / filename
            pdf_path.write_bytes(pdf_bytes)
            out_path = Path(tmp) / "result.json"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tech_support_knowledge._docling_worker",
                    str(pdf_path),
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if proc.returncode != 0 or not out_path.exists():
                stderr_tail = (proc.stderr or "").strip()[-800:]
                if proc.returncode < 0:
                    sig = -proc.returncode
                    name = signal.Signals(sig).name if sig in iter(signal.Signals) else str(sig)
                    hint = ""
                    if name == "SIGILL":
                        hint = (
                            " This is a native illegal-instruction crash, commonly caused by "
                            "Docker Desktop <4.39 on Apple Silicon. Update Docker Desktop to "
                            "4.39+ or run the API on the host."
                        )
                    elif name == "SIGKILL":
                        hint = (
                            " This is usually an out-of-memory kill. Keep KB_PDF_OCR_ENABLED=false "
                            "(default), raise Docker Desktop memory, or free other containers."
                        )
                    raise RuntimeError(
                        f"Docling PDF conversion crashed (signal {sig}/{name}).{hint} "
                        f"stderr: {stderr_tail}"
                    )
                raise RuntimeError(
                    f"Docling PDF conversion failed (exit {proc.returncode}). "
                    f"stderr: {stderr_tail}"
                )

            payload = json.loads(out_path.read_text(encoding="utf-8"))

        return ConversionResult(
            markdown=payload["markdown"],
            converter_name="docling",
            converter_version=str(payload.get("version", "unknown")),
        )


def get_pdf_converter(name: str = "docling") -> PdfToMarkdownConverter:
    selected = name.lower()
    if selected == "docling":
        return DoclingConverter()
    raise ValueError(f"Unsupported PDF_TO_MARKDOWN_CONVERTER: {name}")
