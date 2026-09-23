from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.services.storage.artifact_storage import open_temp_upload_handle


SUPPORTED_DECK_UPLOADS = {
    ".pdf": "application/pdf",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
GENERIC_UPLOAD_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
MAX_DECK_UPLOAD_SIZE_BYTES = 200 * 1024 * 1024
READ_CHUNK_SIZE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class LimitedUpload:
    path: Path
    size: int
    checksum_sha256: str


def detect_supported_deck_extension(file_name: str, content_type: str) -> str | None:
    lowered_name = file_name.lower()
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    matched_extension = next(
        (extension for extension in SUPPORTED_DECK_UPLOADS if lowered_name.endswith(extension)),
        None,
    )
    if matched_extension is None:
        return None
    expected_type = SUPPORTED_DECK_UPLOADS[matched_extension]
    if normalized_content_type in GENERIC_UPLOAD_MIME_TYPES or normalized_content_type == expected_type:
        return matched_extension
    return None


def require_supported_deck_upload(file_name: str, content_type: str) -> str:
    extension = detect_supported_deck_extension(file_name, content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, PPT, and PPTX uploads are supported",
        )
    return extension


async def read_limited_upload(
    file: UploadFile,
    max_size: int = MAX_DECK_UPLOAD_SIZE_BYTES,
    *,
    too_large_detail: str = "Deck uploads must be 200MB or smaller",
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(READ_CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=too_large_detail,
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def stream_limited_upload(file: UploadFile, max_size: int = MAX_DECK_UPLOAD_SIZE_BYTES) -> LimitedUpload:
    handle, temp_path = open_temp_upload_handle()
    total = 0
    digest = hashlib.sha256()
    try:
        with handle:
            while True:
                # Starlette treats a plain BytesIO-backed UploadFile as
                # disk-backed because BytesIO has no SpooledTemporaryFile
                # ``_rolled`` marker. Calling UploadFile.read() would then
                # cross the thread-pool boundary even though the bytes are
                # already in memory. Read that one safe in-memory type
                # directly; retain UploadFile.read() for real multipart files
                # so disk I/O stays off the event loop.
                chunk = (
                    file.file.read(READ_CHUNK_SIZE_BYTES)
                    if isinstance(file.file, BytesIO)
                    else await file.read(READ_CHUNK_SIZE_BYTES)
                )
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Deck uploads must be 200MB or smaller",
                    )
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return LimitedUpload(path=temp_path, size=total, checksum_sha256=digest.hexdigest())
