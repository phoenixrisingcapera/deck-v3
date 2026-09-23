from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import settings


def _validate_key(key: str) -> str:
    path = Path(key)
    if not key or path.is_absolute() or ".." in path.parts:
        raise ValueError("Bucket artifact key is invalid")
    return path.as_posix()


class BucketArtifactService:
    def make_render_schema_key(
        self,
        *,
        user_id: str,
        deck_id: str,
        design_version_id: str,
        generated_slide_id: str,
        code_version_id: str,
    ) -> str:
        return (
            f"users/{user_id}/decks/{deck_id}/"
            f"design-versions/{design_version_id}/"
            f"slides/{generated_slide_id}/"
            f"code-versions/{code_version_id}/render_schema.json"
        )

    def make_code_key(
        self,
        *,
        user_id: str,
        deck_id: str,
        design_version_id: str,
        generated_slide_id: str,
        code_version_id: str,
    ) -> str:
        return (
            f"users/{user_id}/decks/{deck_id}/"
            f"design-versions/{design_version_id}/"
            f"slides/{generated_slide_id}/"
            f"code-versions/{code_version_id}/code.json"
        )

    def make_thumbnail_key(
        self,
        *,
        user_id: str,
        deck_id: str,
        design_version_id: str,
        generated_slide_id: str,
        code_version_id: str,
    ) -> str:
        return (
            f"users/{user_id}/decks/{deck_id}/"
            f"design-versions/{design_version_id}/"
            f"slides/{generated_slide_id}/"
            f"code-versions/{code_version_id}/thumbnail.png"
        )

    def make_manifest_key(self, *, user_id: str, deck_id: str, design_version_id: str) -> str:
        return f"users/{user_id}/decks/{deck_id}/design-versions/{design_version_id}/manifest.json"

    def make_llm_artifact_key(self, *, user_id: str, deck_id: str, artifact_id: str) -> str:
        return f"users/{user_id}/decks/{deck_id}/llm-artifacts/{artifact_id}.json"

    def make_export_key(self, *, user_id: str, deck_id: str, export_id: str, filename: str = "deck.pdf") -> str:
        return f"users/{user_id}/decks/{deck_id}/exports/{export_id}/{filename}"

    async def put_json(self, *, key: str, data: dict, content_type: str = "application/json") -> None:
        self.put_json_sync(key=key, data=data, content_type=content_type)

    async def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.put_bytes_sync(key=key, data=data, content_type=content_type)

    async def create_signed_url(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        return self.create_signed_url_sync(key=key, expires_in_seconds=expires_in_seconds)

    async def delete_object(self, *, key: str) -> None:
        self.delete_object_sync(key=key)

    async def archive_object(self, *, key: str) -> str | None:
        return self.archive_object_sync(key=key)

    async def object_exists(self, *, key: str) -> bool:
        return self.object_exists_sync(key=key)

    def put_json_sync(self, *, key: str, data: dict, content_type: str = "application/json") -> None:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.put_bytes_sync(key=key, data=body, content_type=content_type)

    def put_bytes_sync(self, *, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def create_signed_url_sync(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        raise NotImplementedError

    def delete_object_sync(self, *, key: str) -> None:
        raise NotImplementedError

    def archive_object_sync(self, *, key: str) -> str | None:
        archive_key = f"archived/{_validate_key(key)}"
        if not self.object_exists_sync(key=key):
            return None
        payload = self.get_bytes_sync(key=key)
        self.put_bytes_sync(key=archive_key, data=payload, content_type="application/octet-stream")
        self.delete_object_sync(key=key)
        return archive_key

    def object_exists_sync(self, *, key: str) -> bool:
        raise NotImplementedError

    def get_bytes_sync(self, *, key: str) -> bytes:
        raise NotImplementedError


class LocalBucketArtifactService(BucketArtifactService):
    def _path(self, key: str) -> Path:
        clean_key = _validate_key(key)
        root = Path(settings.uploads_root).resolve()
        path = (root / clean_key).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("Bucket artifact key is invalid") from exc
        return path

    def put_bytes_sync(self, *, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Replace through a sibling temporary file. Local development commonly
        # mounts this directory into containers whose runtime UID differs from
        # the host UID. Reopening an existing artifact in-place then fails even
        # when the containing directory is writable. A same-directory atomic
        # replace only requires directory write permission and also prevents
        # readers from observing a partially written JSON/artifact payload.
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def create_signed_url_sync(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        return f"/api/artifacts/local/{quote(_validate_key(key), safe='/')}"

    def delete_object_sync(self, *, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def archive_object_sync(self, *, key: str) -> str | None:
        source = self._path(key)
        if not source.exists():
            return None
        archive_key = f"archived/{_validate_key(key)}"
        target = self._path(archive_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return archive_key

    def object_exists_sync(self, *, key: str) -> bool:
        return self._path(key).exists()

    def get_bytes_sync(self, *, key: str) -> bytes:
        return self._path(key).read_bytes()


class S3BucketArtifactService(BucketArtifactService):
    def __init__(self, app_settings: Any = settings) -> None:
        self.bucket = app_settings.upload_storage_s3_bucket
        self.signed_url_ttl = app_settings.deck_aistack_signed_url_ttl_seconds
        self.provider = str(getattr(app_settings, "upload_storage_s3_provider", "aws") or "aws").strip().lower()
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 and botocore are required for S3 bucket artifacts") from exc

        self.client = boto3.client(
            "s3",
            region_name=app_settings.upload_storage_s3_region or None,
            endpoint_url=app_settings.upload_storage_s3_endpoint_url or None,
            aws_access_key_id=app_settings.effective_s3_access_key or None,
            aws_secret_access_key=app_settings.effective_s3_secret_key or None,
            # Keep signed artifact URLs on the same deterministic Tigris/S3
            # host contract as upload promotion and worker object access.
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def put_bytes_sync(self, *, key: str, data: bytes, content_type: str) -> None:
        parameters = dict(
            Bucket=self.bucket,
            Key=_validate_key(key),
            Body=data,
            ContentType=content_type,
        )
        if self.provider == "aws":
            parameters["ServerSideEncryption"] = "AES256"
        self.client.put_object(**parameters)

    def create_signed_url_sync(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": _validate_key(key)},
            ExpiresIn=expires_in_seconds or self.signed_url_ttl,
        )

    def delete_object_sync(self, *, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=_validate_key(key))

    def archive_object_sync(self, *, key: str) -> str | None:
        clean_key = _validate_key(key)
        if not self.object_exists_sync(key=clean_key):
            return None
        archive_key = f"archived/{clean_key}"
        self.client.copy_object(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": clean_key},
            Key=archive_key,
            ServerSideEncryption="AES256",
        )
        self.delete_object_sync(key=clean_key)
        return archive_key

    def object_exists_sync(self, *, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_validate_key(key))
            return True
        except Exception:
            return False

    def get_bytes_sync(self, *, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=_validate_key(key))
        return response["Body"].read()


class SupabaseBucketArtifactService(BucketArtifactService):
    def _object_url(self, key: str) -> str:
        bucket = quote(settings.supabase_storage_bucket.strip("/"), safe="")
        object_key = quote(_validate_key(key), safe="/")
        return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{object_key}"

    def _headers(self, *, content_type: str = "application/octet-stream") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": content_type,
        }

    def put_bytes_sync(self, *, key: str, data: bytes, content_type: str) -> None:
        request = Request(
            self._object_url(key),
            data=data,
            headers={**self._headers(content_type=content_type), "x-upsert": "true"},
            method="POST",
        )
        with urlopen(request, timeout=30):
            pass

    def create_signed_url_sync(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        ttl = expires_in_seconds or settings.deck_aistack_signed_url_ttl_seconds
        url = f"{self._object_url(key)}/sign/{ttl}"
        request = Request(url, headers=self._headers(content_type="application/json"), method="POST")
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        signed_url = payload.get("signedURL") or payload.get("signedUrl")
        if not isinstance(signed_url, str):
            raise RuntimeError("Supabase did not return a signed URL")
        if signed_url.startswith("http"):
            return signed_url
        return f"{settings.supabase_url.rstrip('/')}{signed_url}"

    def delete_object_sync(self, *, key: str) -> None:
        request = Request(self._object_url(key), headers=self._headers(), method="DELETE")
        with urlopen(request, timeout=30):
            pass

    def object_exists_sync(self, *, key: str) -> bool:
        request = Request(self._object_url(key), headers=self._headers(), method="HEAD")
        try:
            with urlopen(request, timeout=30):
                return True
        except HTTPError as exc:
            if exc.code == 404:
                return False
            return False
        except Exception:
            return False

    def get_bytes_sync(self, *, key: str) -> bytes:
        request = Request(self._object_url(key), headers=self._headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            return response.read()


def get_bucket_artifact_service() -> BucketArtifactService:
    if settings.upload_storage_backend == "s3":
        return S3BucketArtifactService(settings)
    if settings.upload_storage_backend == "supabase":
        return SupabaseBucketArtifactService()
    return LocalBucketArtifactService()
