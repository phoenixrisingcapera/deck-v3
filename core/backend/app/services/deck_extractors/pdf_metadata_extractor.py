from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


_PAGE_SIZE_PATTERN = re.compile(r"Page\s+(\d+)\s+size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts", re.IGNORECASE)
_GENERIC_PAGE_SIZE_PATTERN = re.compile(r"^Page\s+size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts", re.IGNORECASE | re.MULTILINE)


def extract_pdf_page_metadata(pdf_path: Path) -> list[dict]:
    # PyMuPDF is also the canonical Miniatures renderer. Using it first keeps
    # source-extraction page coverage identical to the pages Miniatures will
    # later enumerate. `pdfinfo -box` may omit per-page entries for PDFs whose
    # pages share dimensions, which previously allowed extraction to persist
    # fewer DeckSlide rows than Miniatures required.
    pymupdf_error: ValueError | None = None
    try:
        return _extract_pdf_page_metadata_with_pymupdf(pdf_path)
    except ValueError as exc:
        pymupdf_error = exc

    if shutil.which("pdfinfo") is None:
        raise ValueError(
            f"PDF metadata extraction failed: PyMuPDF failed: {pymupdf_error}; "
            "pdfinfo is not installed in the backend runtime"
        ) from pymupdf_error

    try:
        return _extract_pdf_page_metadata_with_pdfinfo(pdf_path)
    except ValueError as exc:
        raise ValueError(
            f"PDF metadata extraction failed: PyMuPDF failed: {pymupdf_error}; pdfinfo fallback failed: {exc}"
        ) from exc


def _extract_pdf_page_metadata_with_pdfinfo(pdf_path: Path) -> list[dict]:
    command = ["pdfinfo", "-box", str(pdf_path)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"pdfinfo failed: {(result.stderr or result.stdout).strip() or 'unknown error'}")

    metadata: dict[int, dict] = {}
    for match in _PAGE_SIZE_PATTERN.finditer(result.stdout):
        page_number = int(match.group(1))
        metadata[page_number] = {
            "pageNumber": page_number,
            "widthPoints": float(match.group(2)),
            "heightPoints": float(match.group(3)),
        }

    pages_line = next((line for line in result.stdout.splitlines() if line.lower().startswith("pages:")), None)
    if not pages_line:
        return [metadata[key] for key in sorted(metadata)]

    page_count = int(pages_line.split(":", 1)[1].strip())
    generic_size = _GENERIC_PAGE_SIZE_PATTERN.search(result.stdout)
    generic_width = float(generic_size.group(1)) if generic_size else None
    generic_height = float(generic_size.group(2)) if generic_size else None

    if not metadata:
        return [
            {"pageNumber": page_number, "widthPoints": generic_width, "heightPoints": generic_height}
            for page_number in range(1, page_count + 1)
        ]

    for page_number in range(1, page_count + 1):
        metadata.setdefault(
            page_number,
            {"pageNumber": page_number, "widthPoints": generic_width, "heightPoints": generic_height},
        )

    return [metadata[key] for key in sorted(metadata)]


def _extract_pdf_page_metadata_with_pymupdf(pdf_path: Path) -> list[dict]:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PyMuPDF is not installed") from exc

    pages: list[dict] = []
    try:
        with fitz.open(pdf_path) as document:
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                rectangle = page.rect
                pages.append(
                    {
                        "pageNumber": page_index + 1,
                        "widthPoints": float(rectangle.width),
                        "heightPoints": float(rectangle.height),
                    }
                )
    except Exception as exc:
        raise ValueError(str(exc) or "unknown PyMuPDF metadata error") from exc

    return pages


def extract_pdf_vector_colors_by_page(pdf_path: Path) -> dict[int, list[str]]:
    """Return exact RGB drawing colours from a PDF without raster sampling."""
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PyMuPDF is not installed") from exc

    colors: dict[int, list[str]] = {}
    try:
        with fitz.open(pdf_path) as document:
            for page_index, page in enumerate(document):
                values: list[str] = []
                for drawing in page.get_drawings():
                    for value in (drawing.get("fill"), drawing.get("color")):
                        if not isinstance(value, tuple) or len(value) < 3:
                            continue
                        rgb = tuple(max(0, min(255, round(channel * 255))) for channel in value[:3])
                        values.append("#{:02X}{:02X}{:02X}".format(*rgb))
                text = page.get_text("dict")
                for block in text.get("blocks", []):
                    for line in block.get("lines", []) if isinstance(block, dict) else []:
                        for span in line.get("spans", []) if isinstance(line, dict) else []:
                            value = span.get("color") if isinstance(span, dict) else None
                            if isinstance(value, int):
                                values.append(f"#{value & 0xFFFFFF:06X}")
                colors[page_index + 1] = list(dict.fromkeys(values))
    except Exception as exc:
        raise ValueError(str(exc) or "PDF vector-colour extraction failed") from exc
    return colors


def extract_pdf_font_usage_by_page(pdf_path: Path) -> dict[int, list[dict]]:
    """Preserve observed PDF fonts independently of text-block reconstruction."""
    import fitz

    pages = {}
    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, 1):
            usage: dict[str, int] = {}
            text = page.get_text('dict', flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)
            for block in text.get('blocks', []):
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        family = re.sub(r'^[A-Z]{6}\+', '', str(span.get('font') or '')).strip()
                        weight = len(str(span.get('text') or '').strip())
                        if family and weight:
                            usage[family] = usage.get(family, 0) + weight
            pages[page_number] = [
                {'family': family, 'weightedUsage': weight}
                for family, weight in sorted(usage.items(), key=lambda item: (-item[1], item[0]))
            ]
    return pages
