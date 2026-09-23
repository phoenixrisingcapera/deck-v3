from pathlib import Path
from io import BytesIO
import asyncio
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.storage.upload_scan import (
    UploadScanInfectedError,
    UploadScannerUnavailableError,
    scan_upload_path,
)
from app.services.storage.upload_security import require_supported_deck_upload, stream_limited_upload


def _completed(exit_code: int) -> CompletedProcess[str]:
    return CompletedProcess(["clamscan"], exit_code, stdout="", stderr="")


@pytest.mark.parametrize("exit_code", [2, 70, -9])
def test_scanner_operational_errors_are_not_classified_as_malware(exit_code: int) -> None:
    with (
        patch("app.services.storage.upload_scan.settings.upload_security_scan_command", "clamscan"),
        patch("app.services.storage.upload_scan.subprocess.run", return_value=_completed(exit_code)),
        pytest.raises(UploadScannerUnavailableError),
    ):
        scan_upload_path(Path("customer.pdf"))


def test_scanner_exit_one_is_the_only_malware_verdict() -> None:
    with (
        patch("app.services.storage.upload_scan.settings.upload_security_scan_command", "clamscan"),
        patch("app.services.storage.upload_scan.subprocess.run", return_value=_completed(1)),
        pytest.raises(UploadScanInfectedError),
    ):
        scan_upload_path(Path("customer.pdf"))


def test_scanner_exit_zero_returns_clean_verdict() -> None:
    with (
        patch("app.services.storage.upload_scan.settings.upload_security_scan_command", "clamscan"),
        patch("app.services.storage.upload_scan.subprocess.run", return_value=_completed(0)),
    ):
        result = scan_upload_path(Path("customer.pdf"))

    assert result["status"] == "clean"
    assert result["exitCode"] == 0


@pytest.mark.parametrize(
    "failure",
    [FileNotFoundError("missing scanner"), TimeoutExpired(["clamscan"], timeout=30)],
)
def test_missing_or_timed_out_scanner_fails_closed(failure: Exception) -> None:
    with (
        patch("app.services.storage.upload_scan.settings.upload_security_scan_command", "clamscan"),
        patch("app.services.storage.upload_scan.subprocess.run", side_effect=failure),
        pytest.raises(UploadScannerUnavailableError),
    ):
        scan_upload_path(Path("customer.pdf"))


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("customer.exe", "application/octet-stream"),
        ("customer.pdf", "application/x-msdownload"),
        ("customer.pptx", "application/pdf"),
    ],
)
def test_unsupported_extension_or_mime_is_rejected(filename: str, content_type: str) -> None:
    with pytest.raises(HTTPException) as raised:
        require_supported_deck_upload(filename, content_type)
    assert raised.value.status_code == 415


def test_streaming_upload_rejects_oversized_content_and_removes_temp_file(tmp_path, monkeypatch) -> None:
    temp_path = tmp_path / "oversized-upload.bin"
    monkeypatch.setattr(
        "app.services.storage.upload_security.open_temp_upload_handle",
        lambda: (temp_path.open("wb"), temp_path),
    )
    upload = UploadFile(filename="customer.pdf", file=BytesIO(b"12345"))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(stream_limited_upload(upload, max_size=4))
    assert raised.value.status_code == 413
    assert not temp_path.exists()
