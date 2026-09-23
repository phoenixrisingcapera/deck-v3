from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping


EMBEDDING_SOURCE_CONTRACT_VERSION = "deck-embedding-source.v1"
EMBEDDING_NORMALIZER_VERSION = "deck-artifact-normalizer.v1"
EMBEDDING_CORPUS_VERSION = "openai-3-small-1024.v1"
EMBEDDING_INTENT_CONTRACT_VERSION = "deck-embedding-intent.v1"

INTENT_UPSERT = "upsert"
INTENT_SUPERSEDE = "supersede"
INTENT_REBUILD = "rebuild"
INTENT_OPERATIONS = frozenset({INTENT_UPSERT, INTENT_SUPERSEDE, INTENT_REBUILD})

SOURCE_EXTRACTION = "source_extraction"
ACCEPTED_SMART_EDIT = "accepted_smart_edit"
ACCEPTED_SLIDE_VERSION = "accepted_slide_version"
APPLIED_DESIGN_VERSION = "applied_design_version"
GENERATED_SLIDE = "generated_slide"
VALIDATED_ARTIFACT = "validated_artifact"

SOURCE_TYPES = frozenset(
    {
        SOURCE_EXTRACTION,
        ACCEPTED_SMART_EDIT,
        ACCEPTED_SLIDE_VERSION,
        APPLIED_DESIGN_VERSION,
        GENERATED_SLIDE,
        VALIDATED_ARTIFACT,
    }
)

ELIGIBLE_STATES = MappingProxyType(
    {
        SOURCE_EXTRACTION: frozenset({"completed"}),
        ACCEPTED_SMART_EDIT: frozenset({"accepted", "applied", "edited"}),
        ACCEPTED_SLIDE_VERSION: frozenset({"accepted", "applied"}),
        APPLIED_DESIGN_VERSION: frozenset({"applied", "restored"}),
        GENERATED_SLIDE: frozenset({"current", "applied"}),
        VALIDATED_ARTIFACT: frozenset({"ready", "validated"}),
    }
)

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bucket_payload_key",
    "bucket_render_schema_key",
    "bucket_code_key",
    "bucket_thumbnail_key",
    "credential",
    "password",
    "provider_payload",
    "raw_provider",
    "reasoning",
    "secret",
    "storage_path",
    "token",
    "url",
)


@dataclass(frozen=True, slots=True)
class EmbeddingSourceEnvelope:
    workspace_id: str
    deck_id: str
    source_type: str
    source_id: str
    source_version: str
    schema_version: str
    lifecycle_state: str
    content_hash: str
    normalized_content: Mapping[str, Any]
    provenance: Mapping[str, Any]
    contract_version: str = EMBEDDING_SOURCE_CONTRACT_VERSION
    normalizer_version: str = EMBEDDING_NORMALIZER_VERSION

    @property
    def eligible(self) -> bool:
        return self.lifecycle_state in ELIGIBLE_STATES[self.source_type]

    @property
    def identity_key(self) -> str:
        return ":".join(
            (
                self.workspace_id,
                self.deck_id,
                self.source_type,
                self.source_id,
                self.source_version,
                self.schema_version,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "normalizerVersion": self.normalizer_version,
            "workspaceId": self.workspace_id,
            "deckId": self.deck_id,
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "sourceVersion": self.source_version,
            "schemaVersion": self.schema_version,
            "lifecycleState": self.lifecycle_state,
            "eligible": self.eligible,
            "contentHash": self.content_hash,
            "normalizedContent": _thaw(self.normalized_content),
            "provenance": _thaw(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class EmbeddingIndexingIntent:
    operation: str
    corpus_version: str
    source_identity_key: str
    source_content_hash: str
    payload: Mapping[str, Any]
    contract_version: str = EMBEDDING_INTENT_CONTRACT_VERSION

    @property
    def idempotency_key(self) -> str:
        digest = hashlib.sha256(
            canonical_json_bytes(
                {
                    "contractVersion": self.contract_version,
                    "corpusVersion": self.corpus_version,
                    "operation": self.operation,
                    "sourceIdentityKey": self.source_identity_key,
                    "sourceContentHash": self.source_content_hash,
                }
            )
        ).hexdigest()
        return f"embedding-index:{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "operation": self.operation,
            "corpusVersion": self.corpus_version,
            "idempotencyKey": self.idempotency_key,
            "sourceIdentityKey": self.source_identity_key,
            "sourceContentHash": self.source_content_hash,
            "source": _thaw(self.payload),
        }


def build_embedding_source_envelope(
    *,
    workspace_id: str,
    deck_id: str,
    source_type: str,
    source_id: str,
    source_version: str,
    schema_version: str,
    lifecycle_state: str,
    content: Mapping[str, Any],
    provenance: Mapping[str, Any] | None = None,
) -> EmbeddingSourceEnvelope:
    identifiers = {
        "workspace_id": workspace_id,
        "deck_id": deck_id,
        "source_id": source_id,
        "source_version": source_version,
        "schema_version": schema_version,
        "lifecycle_state": lifecycle_state,
    }
    for field, value in identifiers.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Unsupported embedding source type: {source_type}")
    if not isinstance(content, Mapping):
        raise TypeError("content must be a mapping")
    if provenance is not None and not isinstance(provenance, Mapping):
        raise TypeError("provenance must be a mapping")

    normalized_content = normalize_embedding_source_content(content)
    if not normalized_content:
        raise ValueError("content must contain at least one indexable value")
    normalized_provenance = normalize_embedding_source_content(provenance or {})
    content_hash = hashlib.sha256(canonical_json_bytes(normalized_content)).hexdigest()
    return EmbeddingSourceEnvelope(
        workspace_id=workspace_id.strip(),
        deck_id=deck_id.strip(),
        source_type=source_type,
        source_id=source_id.strip(),
        source_version=source_version.strip(),
        schema_version=schema_version.strip(),
        lifecycle_state=lifecycle_state.strip(),
        content_hash=content_hash,
        normalized_content=_freeze(normalized_content),
        provenance=_freeze(normalized_provenance),
    )


def build_embedding_indexing_intent(
    envelope: EmbeddingSourceEnvelope,
    *,
    operation: str = INTENT_UPSERT,
    corpus_version: str = EMBEDDING_CORPUS_VERSION,
) -> EmbeddingIndexingIntent:
    if operation not in INTENT_OPERATIONS:
        raise ValueError(f"Unsupported embedding intent operation: {operation}")
    if not isinstance(corpus_version, str) or not corpus_version.strip():
        raise ValueError("corpus_version must be a non-empty string")
    if operation == INTENT_UPSERT and not envelope.eligible:
        raise ValueError("Ineligible embedding source cannot create an upsert intent")

    source_payload = envelope.to_dict()
    # Intents carry source identity and normalized content, never vectors or credentials.
    return EmbeddingIndexingIntent(
        operation=operation,
        corpus_version=corpus_version.strip(),
        source_identity_key=envelope.identity_key,
        source_content_hash=envelope.content_hash,
        payload=_freeze(source_payload),
    )


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def normalize_embedding_source_content(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _normalize_value(value)
    return normalized if isinstance(normalized, dict) else {}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key in sorted(value, key=lambda item: str(item)):
            key = str(raw_key).strip()
            if not key or _is_sensitive_key(key):
                continue
            child = _normalize_value(value[raw_key])
            if child not in (None, "", [], {}):
                normalized[key] = child
        return normalized
    if isinstance(value, (list, tuple)):
        return [child for item in value if (child := _normalize_value(item)) not in (None, "", [], {})]
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"Unsupported embedding source value: {type(value).__name__}")


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value
