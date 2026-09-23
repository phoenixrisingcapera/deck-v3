from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_pdf_page_ocr_text(pdf_path: Path, page_number: int) -> str:
    if shutil.which("pdftoppm") is None:
        raise ValueError("PDF OCR fallback requires pdftoppm to be installed in the backend runtime")
    if shutil.which("tesseract") is None:
        raise ValueError("PDF OCR fallback requires tesseract to be installed in the backend runtime")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_prefix = Path(tmpdir) / f"page_{page_number}"
        render_result = subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-r",
                "200",
                "-png",
                "-singlefile",
                str(pdf_path),
                str(output_prefix),
            ],
            capture_output=True,
            text=True,
        )
        image_path = output_prefix.with_suffix(".png")
        if render_result.returncode != 0 or not image_path.exists():
            raise ValueError(
                f"PDF OCR render failed for page {page_number}: "
                f"{(render_result.stderr or render_result.stdout).strip() or 'unknown error'}"
            )

        ocr_result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
        )
        if ocr_result.returncode != 0:
            raise ValueError(
                f"PDF OCR failed for page {page_number}: "
                f"{(ocr_result.stderr or ocr_result.stdout).strip() or 'unknown error'}"
            )

    return ocr_result.stdout.strip()
