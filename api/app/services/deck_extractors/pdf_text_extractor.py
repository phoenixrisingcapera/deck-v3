from __future__ import annotations

import subprocess
import shutil
from pathlib import Path


def _extract_page_text(pdf_path: Path, page_number: int) -> str:
    if shutil.which("pdftotext") is None:
        return _extract_page_text_with_pymupdf(pdf_path, page_number)

    command = [
        "pdftotext",
        "-layout",
        "-enc",
        "UTF-8",
        "-f",
        str(page_number),
        "-l",
        str(page_number),
        str(pdf_path),
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        fallback_error = (result.stderr or result.stdout).strip() or "unknown error"
        try:
            return _extract_page_text_with_pymupdf(pdf_path, page_number)
        except ValueError as exc:
            raise ValueError(
                f"pdftotext failed for page {page_number}: {fallback_error}; PyMuPDF fallback failed: {exc}"
            ) from exc
    return result.stdout.replace("\x0c", "").strip()


def _extract_page_text_with_pymupdf(pdf_path: Path, page_number: int) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PyMuPDF is not installed") from exc

    try:
        with fitz.open(pdf_path) as document:
            if page_number < 1 or page_number > document.page_count:
                raise ValueError(f"Page {page_number} is out of range for a document with {document.page_count} pages")
            page = document.load_page(page_number - 1)
            return page.get_text("text").replace("\x0c", "").strip()
    except Exception as exc:
        raise ValueError(str(exc) or "unknown PyMuPDF text error") from exc


def extract_pdf_text_by_page(pdf_path: Path, page_numbers: list[int]) -> list[dict]:
    pages: list[dict] = []
    for page_number in page_numbers:
        pages.append({"pageNumber": page_number, "text": _extract_page_text(pdf_path, page_number)})
    return pages
