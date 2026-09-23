from __future__ import annotations

import os
import time
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Iterator, Protocol

from app.core.config import settings
from app.core.security import generate_id


@dataclass(frozen=True)
class StoredUpload:
    provider: str
    storage_path: str
    path: Path


class UploadStorage(Protocol):
    provider: str

    def root(self) -> Path: ...

    def resolve_path(self, storage_path: str | None) -> Path | None: ...

    def create_incoming_temp(self, *, suffix: str = ".tmp") -> tuple[int, Path]: ...

    def generated_name(self, prefix: str, suffix: str) -> str: ...

    def write_bytes(self, storage_path: str, payload: bytes) -> StoredUpload: ...

    def move_file(self, source_path: Path, storage_path: str) -> StoredUpload: ...

    def object_metadata(self, storage_path: str) -> dict: ...

    def iter_bytes(self, storage_path: str, *, chunk_size: int) -> Iterator[bytes]: ...

    def list_objects(self, prefix: str = "") -> list[dict]: ...

    def create_signed_get_url(self, storage_path: str, *, expires_in: int | None = None) -> str: ...

    def create_signed_put_url(
        self,
        storage_path: str,
        *,
        content_type: str = "application/octet-stream",
        expires_in: int | None = None,
    ) -> str: ...

    def promote(self, stored: StoredUpload) -> StoredUpload: ...

    def delete(self, storage_path: str) -> None: ...
    def object_exists(self, storage_path: str) -> bool: ...


def _validate_relative_storage_path(storage_path: str | None) -> Path | None:
    if not storage_path:
        return None

    relative_path = Path(storage_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    return relative_path


def _retryable_storage_call(operation_name: str, callback):
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return callback()
        except Exception as exc:
            last_exc = exc
            if attempt == 2:
                break
            time.sleep(0.15 * (2**attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{operation_name} failed")


class LocalUploadStorage:
    provider = "local"

    def root(self) -> Path:
        path = Path(settings.uploads_root)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_path(self, storage_path: str | None) -> Path | None:
        relative_path = _validate_relative_storage_path(storage_path)
        if relative_path is None:
            return None

        root = self.root().resolve()
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate

    def create_incoming_temp(self, *, suffix: str = ".tmp") -> tuple[int, Path]:
        incoming_dir = self.root() / "incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="upload_", suffix=suffix, dir=incoming_dir)
        return fd, Path(temp_name)

    def generated_name(self, prefix: str, suffix: str) -> str:
        clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        if clean_suffix == ".":
            clean_suffix = ".bin"
        return f"{generate_id(prefix)}{clean_suffix}"

    def write_bytes(self, storage_path: str, payload: bytes) -> StoredUpload:
        path = self._require_path(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "xb") as handle:
            handle.write(payload)
        return StoredUpload(provider=self.provider, storage_path=storage_path, path=path)

    def move_file(self, source_path: Path, storage_path: str) -> StoredUpload:
        path = self._require_path(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Upload storage path already exists: {storage_path}")
        source_path.replace(path)
        return StoredUpload(provider=self.provider, storage_path=storage_path, path=path)

    def object_metadata(self, storage_path: str) -> dict:
        path = self._require_path(storage_path)
        if not path.exists():
            raise FileNotFoundError(storage_path)
        return {
            "storagePath": storage_path,
            "contentLength": path.stat().st_size,
            "contentType": None,
            "etag": None,
            "lastModified": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z",
        }

    def iter_bytes(self, storage_path: str, *, chunk_size: int) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("Upload storage chunk size must be positive")
        path = self._require_path(storage_path)
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                yield chunk

    def list_objects(self, prefix: str = "") -> list[dict]:
        relative_prefix = _validate_relative_storage_path(prefix) if prefix else Path("")
        if relative_prefix is None:
            raise ValueError("Upload storage prefix is invalid")
        root = self.root().resolve()
        search_root = (root / relative_prefix).resolve()
        try:
            search_root.relative_to(root)
        except ValueError as exc:
            raise ValueError("Upload storage prefix is invalid") from exc
        if not search_root.exists():
            return []
        objects: list[dict] = []
        for path in search_root.rglob("*"):
            if not path.is_file():
                continue
            relative_path = path.relative_to(root).as_posix()
            objects.append(
                {
                    "storagePath": relative_path,
                    "contentLength": path.stat().st_size,
                    "lastModified": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z",
                }
            )
        return objects

    def create_signed_get_url(self, storage_path: str, *, expires_in: int | None = None) -> str:
        self._require_path(storage_path)
        object_path = quote(storage_path, safe="/")
        return f"/api/uploads/local/{object_path}"

    def create_signed_put_url(
        self,
        storage_path: str,
        *,
        content_type: str = "application/octet-stream",
        expires_in: int | None = None,
    ) -> str:
        raise NotImplementedError("Presigned browser uploads require S3-compatible upload storage")

    def promote(self, stored: StoredUpload) -> StoredUpload:
        return stored

    def delete(self, storage_path: str) -> None:
        path = self.resolve_path(storage_path)
        if path is not None:
            path.unlink(missing_ok=True)

    def object_exists(self, storage_path: str) -> bool:
        path = self.resolve_path(storage_path)
        return bool(path is not None and path.exists())

    def _require_path(self, storage_path: str) -> Path:
        path = self.resolve_path(storage_path)
        if path is None:
            raise ValueError("Upload storage path is invalid")
        return path


class S3UploadStorage(LocalUploadStorage):
    provider = "s3"

    def __init__(self, client: object | None = None) -> None:
        self._client = client

    def _client_or_create(self) -> object:
        if self._client is None:
            validated_endpoint = _validate_s3_runtime_config()
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise RuntimeError("boto3 is required when UPLOAD_STORAGE_BACKEND=s3") from exc

            access_key = settings.effective_s3_access_key
            secret_key = settings.effective_s3_secret_key

            kwargs: dict[str, str] = {}
            # S3-compatible providers must use one deterministic signing and
            # addressing contract for API uploads, workers, and presigned URLs.
            # SigV4 plus path-style addressing avoids SDK/environment defaults
            # changing the canonical host that is included in the signature.
            kwargs["config"] = Config(signature_version="s3v4", s3={"addressing_style": "path"})
            if settings.upload_storage_s3_region:
                kwargs["region_name"] = settings.upload_storage_s3_region
            if validated_endpoint:
                kwargs["endpoint_url"] = validated_endpoint
            if access_key:
                kwargs["aws_access_key_id"] = access_key
            if secret_key:
                kwargs["aws_secret_access_key"] = secret_key
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def _object_key(self, storage_path: str) -> str:
        relative_path = _validate_relative_storage_path(storage_path)
        if relative_path is None:
            raise ValueError("Upload storage path is invalid")

        clean_prefix = settings.upload_storage_s3_prefix.strip("/")
        clean_path = relative_path.as_posix()
        return f"{clean_prefix}/{clean_path}" if clean_prefix else clean_path

    def _cache_path(self, storage_path: str) -> Path:
        path = LocalUploadStorage.resolve_path(self, storage_path)
        if path is None:
            raise ValueError("Upload storage path is invalid")
        return path

    def write_bytes(self, storage_path: str, payload: bytes) -> StoredUpload:
        path = self._cache_path(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "xb") as handle:
            handle.write(payload)
        return StoredUpload(provider=self.provider, storage_path=storage_path, path=path)

    def move_file(self, source_path: Path, storage_path: str) -> StoredUpload:
        path = self._cache_path(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Upload storage path already exists: {storage_path}")
        source_path.replace(path)
        return StoredUpload(provider=self.provider, storage_path=storage_path, path=path)

    def resolve_path(self, storage_path: str | None) -> Path | None:
        path = super().resolve_path(storage_path)
        if path is None or path.exists():
            return path

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            response = _retryable_storage_call(
                "s3.get_object",
                lambda: self._client_or_create().get_object(
                    Bucket=settings.upload_storage_s3_bucket,
                    Key=self._object_key(storage_path or ""),
                ),
            )
            path.write_bytes(response["Body"].read())
        except Exception:
            path.unlink(missing_ok=True)
            return None
        return path

    def object_metadata(self, storage_path: str) -> dict:
        object_key = self._object_key(storage_path)
        response = _retryable_storage_call(
            "s3.head_object",
            lambda: self._client_or_create().head_object(
                Bucket=settings.upload_storage_s3_bucket,
                Key=object_key,
            ),
        )
        return {
            "storagePath": storage_path,
            "objectKey": object_key,
            "contentLength": int(response.get("ContentLength") or 0),
            "contentType": response.get("ContentType"),
            "etag": response.get("ETag"),
            "lastModified": response.get("LastModified").isoformat() if response.get("LastModified") else None,
        }

    def iter_bytes(self, storage_path: str, *, chunk_size: int) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("Upload storage chunk size must be positive")
        response = _retryable_storage_call(
            "s3.get_object",
            lambda: self._client_or_create().get_object(
                Bucket=settings.upload_storage_s3_bucket,
                Key=self._object_key(storage_path),
            ),
        )
        body = response["Body"]
        try:
            while chunk := body.read(chunk_size):
                yield chunk
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

    def list_objects(self, prefix: str = "") -> list[dict]:
        object_prefix = self._object_key(prefix) if prefix else ""
        if object_prefix:
            object_prefix = object_prefix.rstrip("/") + "/"
        paginator = self._client_or_create().get_paginator("list_objects_v2")
        objects: list[dict] = []
        pages = _retryable_storage_call(
            "s3.list_objects_v2",
            lambda: list(
                paginator.paginate(
                    Bucket=settings.upload_storage_s3_bucket,
                    Prefix=object_prefix,
                )
            ),
        )
        clean_storage_prefix = settings.upload_storage_s3_prefix.strip("/")
        strip_prefix = f"{clean_storage_prefix}/" if clean_storage_prefix else ""
        for page in pages:
            for item in page.get("Contents", []):
                key = str(item.get("Key") or "")
                storage_path = key[len(strip_prefix) :] if strip_prefix and key.startswith(strip_prefix) else key
                objects.append(
                    {
                        "storagePath": storage_path,
                        "objectKey": key,
                        "contentLength": int(item.get("Size") or 0),
                        "lastModified": item.get("LastModified").isoformat() if item.get("LastModified") else None,
                        "etag": item.get("ETag"),
                    }
                )
        return objects

    def create_signed_get_url(self, storage_path: str, *, expires_in: int | None = None) -> str:
        ttl = expires_in or settings.deck_aistack_signed_url_ttl_seconds
        return _retryable_storage_call(
            "s3.generate_presigned_get",
            lambda: self._client_or_create().generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": settings.upload_storage_s3_bucket,
                    "Key": self._object_key(storage_path),
                },
                ExpiresIn=ttl,
            ),
        )

    def create_signed_put_url(
        self,
        storage_path: str,
        *,
        content_type: str = "application/octet-stream",
        expires_in: int | None = None,
    ) -> str:
        ttl = expires_in or settings.deck_aistack_signed_url_ttl_seconds
        return _retryable_storage_call(
            "s3.generate_presigned_put",
            lambda: self._client_or_create().generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": settings.upload_storage_s3_bucket,
                    "Key": self._object_key(storage_path),
                    "ContentType": content_type,
                },
                ExpiresIn=ttl,
            ),
        )

    def promote(self, stored: StoredUpload) -> StoredUpload:
        if not stored.path.exists():
            raise FileNotFoundError(stored.path)

        with open(stored.path, "rb") as handle:
            _retryable_storage_call(
                "s3.put_object",
                lambda: (
                    handle.seek(0),
                    self._client_or_create().put_object(
                        Bucket=settings.upload_storage_s3_bucket,
                        Key=self._object_key(stored.storage_path),
                        Body=handle,
                    ),
                )[1],
            )
        return stored

    def delete(self, storage_path: str) -> None:
        super().delete(storage_path)
        _retryable_storage_call(
            "s3.delete_object",
            lambda: self._client_or_create().delete_object(
                Bucket=settings.upload_storage_s3_bucket,
                Key=self._object_key(storage_path),
            ),
        )

    def object_exists(self, storage_path: str) -> bool:
        try:
            self.object_metadata(storage_path)
            return True
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(((response.get("Error") or {}) if isinstance(response, dict) else {}).get("Code") or "")
            status = ((response.get("ResponseMetadata") or {}) if isinstance(response, dict) else {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return False
            raise


class SupabaseUploadStorage(LocalUploadStorage):
    provider = "supabase"

    def _object_url(self, storage_path: str) -> str:
        relative_path = _validate_relative_storage_path(storage_path)
        if relative_path is None:
            raise ValueError("Upload storage path is invalid")
        base_url = settings.supabase_url.rstrip("/")
        bucket = quote(settings.supabase_storage_bucket.strip("/"), safe="")
        object_path = quote(relative_path.as_posix(), safe="/")
        return f"{base_url}/storage/v1/object/{bucket}/{object_path}"

    def _headers(self, *, content_type: str = "application/octet-stream") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": content_type,
        }

    def write_bytes(self, storage_path: str, payload: bytes) -> StoredUpload:
        stored = LocalUploadStorage.write_bytes(self, storage_path, payload)
        return StoredUpload(provider=self.provider, storage_path=stored.storage_path, path=stored.path)

    def move_file(self, source_path: Path, storage_path: str) -> StoredUpload:
        stored = LocalUploadStorage.move_file(self, source_path, storage_path)
        return StoredUpload(provider=self.provider, storage_path=stored.storage_path, path=stored.path)

    def promote(self, stored: StoredUpload) -> StoredUpload:
        if not stored.path.exists():
            raise FileNotFoundError(stored.path)
        request = Request(
            self._object_url(stored.storage_path),
            data=stored.path.read_bytes(),
            headers={**self._headers(content_type="application/octet-stream"), "x-upsert": "false"},
            method="POST",
        )
        with urlopen(request, timeout=30):
            pass
        return StoredUpload(provider=self.provider, storage_path=stored.storage_path, path=stored.path)

    def resolve_path(self, storage_path: str | None) -> Path | None:
        path = super().resolve_path(storage_path)
        if path is None or path.exists():
            return path
        try:
            request = Request(self._object_url(storage_path or ""), headers=self._headers(), method="GET")
            path.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(request, timeout=30) as response:
                path.write_bytes(response.read())
        except Exception:
            path.unlink(missing_ok=True)
            return None
        return path

    def object_metadata(self, storage_path: str) -> dict:
        request = Request(self._object_url(storage_path), headers=self._headers(), method="HEAD")
        with urlopen(request, timeout=30) as response:
            headers = response.headers
            return {
                "storagePath": storage_path,
                "contentLength": int(headers.get("Content-Length") or 0),
                "contentType": headers.get("Content-Type"),
                "etag": headers.get("ETag"),
                "lastModified": headers.get("Last-Modified"),
            }

    def iter_bytes(self, storage_path: str, *, chunk_size: int) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("Upload storage chunk size must be positive")
        request = Request(self._object_url(storage_path), headers=self._headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            while chunk := response.read(chunk_size):
                yield chunk

    def delete(self, storage_path: str) -> None:
        from urllib.error import HTTPError

        super().delete(storage_path)
        request = Request(self._object_url(storage_path), headers=self._headers(), method="DELETE")
        try:
            with urlopen(request, timeout=30):
                pass
        except HTTPError as exc:
            if exc.code != 404:
                raise

    def object_exists(self, storage_path: str) -> bool:
        from urllib.error import HTTPError

        request = Request(self._object_url(storage_path), headers=self._headers(), method="HEAD")
        try:
            with urlopen(request, timeout=30):
                return True
        except HTTPError as exc:
            if exc.code == 404:
                return False
            raise


def _validate_s3_runtime_config() -> str | None:
    missing = []
    if not settings.upload_storage_s3_bucket:
        missing.append("S3_BUCKET_NAME, AWS_S3_BUCKET_NAME, UPLOAD_STORAGE_S3_BUCKET, or RAILWAY_BUCKET_NAME")
    if not settings.upload_storage_s3_region:
        missing.append("AWS_DEFAULT_REGION, UPLOAD_STORAGE_S3_REGION, or RAILWAY_BUCKET_REGION")
    provider = settings.upload_storage_s3_provider.strip().lower()
    endpoint = settings.upload_storage_s3_endpoint_url.strip()
    if provider not in {"aws", "compatible"}:
        missing.append("UPLOAD_STORAGE_S3_PROVIDER or STORAGE_S3_PROVIDER must be aws or compatible")
    elif provider == "compatible" and not endpoint:
        missing.append("AWS_ENDPOINT_URL, UPLOAD_STORAGE_S3_ENDPOINT, or RAILWAY_BUCKET_ENDPOINT")
    elif provider == "aws" and endpoint:
        raise RuntimeError("AWS S3 storage must not set a custom endpoint; use provider=compatible")
    elif provider == "compatible":
        from app.core.instant_html_renderer_security import validate_renderer_storage_endpoint

        try:
            endpoint = validate_renderer_storage_endpoint(
                endpoint,
                backend="s3",
                allowed_hosts=settings.instant_html_storage_allowed_hosts,
                variable_name="UPLOAD_STORAGE_S3_ENDPOINT",
            )
        except ValueError as exc:
            raise RuntimeError("S3-compatible upload storage endpoint is invalid") from exc
    if not settings.effective_s3_access_key:
        missing.append("AWS_ACCESS_KEY_ID, UPLOAD_STORAGE_S3_ACCESS_KEY, or RAILWAY_BUCKET_ACCESS_KEY")
    if not settings.effective_s3_secret_key:
        missing.append("AWS_SECRET_ACCESS_KEY, UPLOAD_STORAGE_S3_SECRET_KEY, or RAILWAY_BUCKET_SECRET_KEY")
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"S3 upload storage is missing required config: {joined}")
    return endpoint if provider == "compatible" else None


def get_upload_storage() -> UploadStorage:
    if settings.upload_storage_backend == "local":
        return LocalUploadStorage()
    if settings.upload_storage_backend == "s3":
        _validate_s3_runtime_config()
        return S3UploadStorage()
    if settings.upload_storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_service_role_key or not settings.supabase_storage_bucket:
            raise RuntimeError("Supabase upload storage is missing SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, or SUPABASE_STORAGE_BUCKET")
        return SupabaseUploadStorage()
    raise ValueError("Unsupported upload storage backend")


def promote_upload(stored: StoredUpload) -> StoredUpload:
    if stored.provider == "local" and settings.upload_storage_backend != "local":
        raise ValueError("Upload storage backend changed before promotion")
    if stored.provider == "s3" and settings.upload_storage_backend != "s3":
        raise ValueError("Upload storage backend changed before promotion")
    if stored.provider == "supabase" and settings.upload_storage_backend != "supabase":
        raise ValueError("Upload storage backend changed before promotion")
    return get_upload_storage().promote(stored)


def open_temp_upload_handle() -> tuple[object, Path]:
    fd, temp_path = get_upload_storage().create_incoming_temp()
    return os.fdopen(fd, "wb"), temp_path
