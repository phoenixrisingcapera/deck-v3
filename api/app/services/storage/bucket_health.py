from __future__ import annotations

from datetime import datetime
from time import perf_counter

from app.core.config import settings
from app.core.security import generate_id
from app.services.storage.artifact_storage import get_upload_storage, promote_upload


def storage_pipeline_health_check() -> dict:
    required_config = {
        "backend": bool(settings.upload_storage_backend),
        "bucket": bool(settings.upload_storage_s3_bucket) if settings.upload_storage_backend == "s3" else True,
        "region": bool(settings.upload_storage_s3_region) if settings.upload_storage_backend == "s3" else True,
        "endpoint": (
            settings.upload_storage_s3_provider == "aws" or bool(settings.upload_storage_s3_endpoint_url)
        ) if settings.upload_storage_backend == "s3" else True,
        "accessKey": bool(settings.effective_s3_access_key) if settings.upload_storage_backend == "s3" else True,
        "secretKey": bool(settings.effective_s3_secret_key) if settings.upload_storage_backend == "s3" else True,
    }
    checks = {
        "bucketConfigPresent": all(required_config.values()),
        "putObject": False,
        "headObject": False,
        "getObject": False,
        "signedGetUrl": False,
        "signedPutUrl": False,
    }
    timings: dict[str, float] = {}
    storage_path = f"admin/storage-health/{generate_id('health')}.txt"
    payload = f"deck-aistack-storage-health {datetime.utcnow().isoformat()}".encode("utf-8")
    details: dict[str, object] = {
        "provider": settings.upload_storage_backend,
        "bucketConfigured": bool(settings.upload_storage_s3_bucket),
        "regionConfigured": bool(settings.upload_storage_s3_region),
        "endpointConfigured": bool(settings.upload_storage_s3_endpoint_url),
        "signedUrlTtlSeconds": settings.deck_aistack_signed_url_ttl_seconds,
        "uploadScanConfigured": bool(settings.upload_security_scan_command),
        "keyPrefix": storage_path.rsplit("/", 1)[0],
    }

    if not checks["bucketConfigPresent"]:
        return {"ok": False, "checks": checks, "details": details}

    try:
        storage = get_upload_storage()
        started = perf_counter()
        stored = storage.write_bytes(storage_path, payload)
        promote_upload(stored)
        checks["putObject"] = True
        timings["putObjectMs"] = round((perf_counter() - started) * 1000, 2)

        started = perf_counter()
        metadata = storage.object_metadata(storage_path)
        checks["headObject"] = int(metadata.get("contentLength") or 0) == len(payload)
        details["contentLength"] = metadata.get("contentLength")
        timings["headObjectMs"] = round((perf_counter() - started) * 1000, 2)

        started = perf_counter()
        resolved_path = storage.resolve_path(storage_path)
        checks["getObject"] = bool(resolved_path and resolved_path.exists() and resolved_path.read_bytes() == payload)
        timings["getObjectMs"] = round((perf_counter() - started) * 1000, 2)

        started = perf_counter()
        signed_get_url = storage.create_signed_get_url(storage_path)
        checks["signedGetUrl"] = signed_get_url.startswith(("http://", "https://", "/api/"))
        timings["signedGetUrlMs"] = round((perf_counter() - started) * 1000, 2)

        started = perf_counter()
        signed_put_url = storage.create_signed_put_url(
            f"admin/storage-health/{generate_id('health_put')}.txt",
            content_type="text/plain",
        )
        checks["signedPutUrl"] = signed_put_url.startswith(("http://", "https://"))
        timings["signedPutUrlMs"] = round((perf_counter() - started) * 1000, 2)
    except Exception as exc:
        details["errorType"] = exc.__class__.__name__
        details["error"] = str(exc)[:300]
    finally:
        try:
            get_upload_storage().delete(storage_path)
        except Exception:
            pass

    return {"ok": all(checks.values()), "checks": checks, "metrics": timings, "details": details}
