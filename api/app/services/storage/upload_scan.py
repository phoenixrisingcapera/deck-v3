from __future__ import annotations

import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings


class UploadScanInfectedError(ValueError):
    """The scanner positively identified malware (scanner exit code 1)."""


class UploadScannerUnavailableError(RuntimeError):
    """The configured scanner could not produce a trustworthy verdict."""


def scan_upload_path(path: Path) -> dict[str, str | int]:
    command = settings.upload_security_scan_command.strip()
    if not command:
        return {"status": "not_configured"}

    args = shlex.split(command)
    if "{path}" in args:
        args = [str(path) if item == "{path}" else item for item in args]
    else:
        args.append(str(path))

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=settings.upload_security_scan_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UploadScannerUnavailableError("Upload security scanner timed out") from exc
    except OSError as exc:
        raise UploadScannerUnavailableError("Upload security scanner is unavailable") from exc

    if result.returncode == 1:
        raise UploadScanInfectedError("Upload security scan detected malware")
    if result.returncode > 1 or result.returncode < 0:
        raise UploadScannerUnavailableError(
            f"Upload security scanner failed with exit code {result.returncode}"
        )

    return {
        "status": "clean",
        "scanner": Path(args[0]).name,
        "exitCode": result.returncode,
        "scannedAt": datetime.now(UTC).isoformat(),
    }
