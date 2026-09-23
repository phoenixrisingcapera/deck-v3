from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from app.core.security import generate_id
from app.db.models import DeckFile
from app.services.storage.artifact_storage import LocalUploadStorage, StoredUpload, get_upload_storage, promote_upload


def _storage_for_file(deck_file: DeckFile):
    if deck_file.storage_provider == "local":
        return LocalUploadStorage()
    return get_upload_storage()


def get_upload_root() -> Path:
    return get_upload_storage().root()


def resolve_upload_path(storage_path: str | None) -> Path | None:
    if not storage_path:
        return None

    return get_upload_storage().resolve_path(storage_path)


def get_stored_file_path(deck_file: DeckFile) -> Path:
    storage_name = deck_file.storage_path or deck_file.filename
    path = _storage_for_file(deck_file).resolve_path(storage_name)
    if path is None and deck_file.storage_provider != get_upload_storage().provider:
        # Recover legacy/provider-drift records by falling back to the current
        # canonical runtime storage when the recorded provider cannot resolve
        # the object but the storage path itself is still canonical.
        path = get_upload_storage().resolve_path(storage_name)
    if path is None:
        raise ValueError("Stored file path is invalid")
    return path


def compute_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deck_storage_prefix(deck_file: DeckFile) -> str | None:
    storage_path = deck_file.storage_path or ""
    parts = storage_path.split("/")
    if len(parts) >= 4 and parts[0] == "users" and parts[2] == "decks":
        return "/".join(parts[:4])
    deck = getattr(deck_file, "deck", None)
    user_id = getattr(deck, "user_id", None)
    if user_id:
        return f"users/{user_id}/decks/{deck_file.deck_id}"
    return None


def _local_output_path(storage_path: str, *, error_message: str) -> Path:
    # Remote storage resolve_path() fetches existing objects. New derived outputs
    # such as converted PDFs need a writable local cache path first, then a
    # promotion step to persist the cache object to S3/Supabase.
    output_path = LocalUploadStorage().resolve_path(storage_path)
    if output_path is None:
        raise ValueError(error_message)
    return output_path


def ensure_pdf_source(deck_file: DeckFile) -> tuple[Path, bool]:
    source_path = get_stored_file_path(deck_file)
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return source_path, False

    if suffix not in {".ppt", ".pptx"}:
        raise ValueError(f"Unsupported source file type for extraction: {suffix or 'unknown'}")

    source_checksum = deck_file.checksum_sha256 or compute_file_sha256(source_path)
    metadata = dict(deck_file.metadata_json or {})
    converted_pdf = metadata.get("convertedPdf")
    if isinstance(converted_pdf, dict) and converted_pdf.get("sourceChecksum") == source_checksum:
        cached_path = _storage_for_file(deck_file).resolve_path(converted_pdf.get("storagePath"))
        if cached_path is not None and cached_path.exists():
            metadata["convertedPdf"] = {
                **converted_pdf,
                "reused": True,
            }
            deck_file.metadata_json = metadata
            return cached_path, True

    storage = _storage_for_file(deck_file)
    deck_prefix = _deck_storage_prefix(deck_file)
    output_storage_path = (
        f"{deck_prefix}/converted/{deck_file.id}_{source_checksum[:16]}.pdf"
        if deck_prefix
        else f"converted/{deck_file.id}_{source_checksum[:16]}.pdf"
    )
    output_path = _local_output_path(output_storage_path, error_message="Converted PDF storage path is invalid")
    if output_path.exists():
        metadata["convertedPdf"] = {
            "sourceChecksum": source_checksum,
            "storageProvider": storage.provider,
            "storagePath": output_storage_path,
            "reused": True,
        }
        deck_file.metadata_json = metadata
        return output_path, True

    if shutil.which("libreoffice") is None:
        raise ValueError("PowerPoint extraction requires LibreOffice to be installed in the backend runtime")

    conversion_dir = storage.root() / "converted"
    conversion_dir.mkdir(parents=True, exist_ok=True)
    temp_input_dir = conversion_dir / f"{generate_id('office_src')}"
    temp_input_dir.mkdir(parents=True, exist_ok=True)
    copied_input = temp_input_dir / source_path.name
    shutil.copy2(source_path, copied_input)

    command = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(conversion_dir),
        str(copied_input),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    generated_pdf = conversion_dir / f"{copied_input.stem}.pdf"
    if result.returncode != 0 or not generated_pdf.exists():
        raise ValueError(
            f"LibreOffice conversion failed for {deck_file.original_filename or deck_file.filename}: "
            f"{(result.stderr or result.stdout).strip() or 'unknown error'}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_pdf.replace(output_path)
    shutil.rmtree(temp_input_dir, ignore_errors=True)
    stored = promote_upload(StoredUpload(provider=storage.provider, storage_path=output_storage_path, path=output_path))
    metadata["convertedPdf"] = {
        "sourceChecksum": source_checksum,
        "storageProvider": stored.provider,
        "storagePath": stored.storage_path,
        "reused": False,
    }
    deck_file.metadata_json = metadata
    return stored.path, True
