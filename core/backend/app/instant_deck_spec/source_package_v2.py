"""Versioned source-intelligence contract for structured deck planning.

Source Package v2 is an additive, offline adapter over the immutable v1
package. It never calls a provider, retrieval service, database, worker, or
network. Customer content remains request-scoped and derived asset bytes are
returned separately from the JSON contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from io import BytesIO
import re
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from .models import (
    BrandRoleRecord,
    DebrisExclusion,
    MissingEvidenceRecord,
    NormalizedSourcePackage,
    SourceClaimRecord,
    SourceConflictRecord,
    SourceEmbeddingPolicy,
    SourceFileIdentity,
    SourceNumberRecord,
    SourceReference,
    SourceSlideRecord,
    StrictModel,
)
from .source_package import canonical_sha256


SOURCE_PACKAGE_VERSION_V2 = "instant-deck-source-package.v2"
WORDMARK_RASTERIZER_VERSION = "instant-deck-wordmark-rasterizer.v1"
MATERIALITY_POLICY_VERSION = "instant-deck-materiality-policy.v1"
ASSET_ROLE_POLICY_VERSION = "instant-deck-asset-role-policy.v1"

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
V2AssetId = Annotated[
    str,
    StringConstraints(pattern=r"^(?:asset_s[0-9]{2}_[0-9]{2}|assetv2_s[0-9]{2}_[a-z0-9_]+)$"),
]


class SourcePackageV2Error(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class FrozenModel(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, str_strip_whitespace=True)


class AssetSemanticRole(str, Enum):
    LITERAL_LOGO = "literal_logo"
    WORDMARK = "wordmark"
    BRAND_SYMBOL = "brand_symbol"
    BRAND_ARCHITECTURE = "brand_architecture"
    EVENT_PHOTOGRAPHY = "event_photography"
    FOUNDER_PORTRAIT = "founder_portrait"
    PROGRAMME_IMAGERY = "programme_imagery"
    EVIDENCE_IMAGE = "evidence_image"
    DIAGRAM = "diagram"


class ProtectedCoverageCategory(str, Enum):
    FINANCIAL = "financial"
    TRACTION = "traction"
    FOUNDER = "founder"
    ASK = "ask"


class MaterialityBand(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    SUPPORTING = "supporting"
    CONTEXTUAL = "contextual"


class NormalizedSourceRegionV2(FrozenModel):
    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    bottom: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "NormalizedSourceRegionV2":
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("source region requires positive width and height")
        return self


class MaterialFactV2(FrozenModel):
    fact_id: Annotated[str, StringConstraints(pattern=r"^fact_s[0-9]{2}_[0-9]{2}$")]
    kind: Literal[
        "identity",
        "positioning",
        "product",
        "process",
        "metric",
        "financial",
        "team",
        "partnership",
        "general",
    ]
    text: Annotated[str, StringConstraints(min_length=1, max_length=2400)]
    material: bool
    materiality_score: int = Field(ge=0, le=100)
    materiality_band: MaterialityBand
    coverage_categories: tuple[ProtectedCoverageCategory, ...]
    planner_protected: bool
    score_reasons: tuple[Annotated[str, StringConstraints(min_length=1, max_length=80)], ...]
    source_reference_ids: tuple[str, ...] = Field(min_length=1, max_length=8)


class SourceAssetRecordV2(FrozenModel):
    asset_id: V2AssetId
    semantic_role: AssetSemanticRole
    role_confidence: float = Field(ge=0, le=1)
    role_reasons: tuple[
        Annotated[str, StringConstraints(min_length=1, max_length=100)], ...
    ] = Field(
        min_length=1,
        max_length=6,
    )
    acquisition: Literal[
        "embedded_raster",
        "embedded_vector",
        "vector_wordmark_rasterized",
        "page_region_rasterized",
    ]
    mime_type: Literal["image/png", "image/jpeg", "image/webp", "image/svg+xml"]
    byte_sha256: Sha256
    width: int = Field(gt=0, le=20000)
    height: int = Field(gt=0, le=20000)
    alt_text: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    source_document_sha256: Sha256
    source_page: int = Field(ge=1, le=500)
    source_region: NormalizedSourceRegionV2 | None
    source_region_sha256: Sha256 | None
    source_reference_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    derived_from_asset_id: str | None
    required_for_planner: bool
    classifier_version: Literal["instant-deck-asset-role-policy.v1"] = ASSET_ROLE_POLICY_VERSION


class SourceBackedBrandMetadataV2(FrozenModel):
    organization_name: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    organization_source_reference_ids: tuple[str, ...] = Field(min_length=0, max_length=8)
    product_candidate: Annotated[str, StringConstraints(min_length=1, max_length=240)] | None
    product_source_reference_ids: tuple[str, ...] = Field(min_length=0, max_length=8)
    audience_candidate: Annotated[str, StringConstraints(min_length=1, max_length=180)] | None
    audience_source_reference_ids: tuple[str, ...] = Field(min_length=0, max_length=8)
    deck_type_candidate: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None
    deck_type_source_reference_ids: tuple[str, ...] = Field(min_length=0, max_length=8)
    roles: tuple[BrandRoleRecord, ...] = Field(min_length=3, max_length=8)
    wordmark_asset_id: V2AssetId | None
    literal_logo_asset_id: V2AssetId | None
    brand_symbol_asset_ids: tuple[V2AssetId, ...]


class ProtectedCoverageV2(FrozenModel):
    category: ProtectedCoverageCategory
    status: Literal["present", "missing"]
    protected_fact_ids: tuple[str, ...]
    number_ids: tuple[str, ...]
    source_slide_ids: tuple[str, ...]
    minimum_planner_slide_mentions: int = Field(ge=0, le=3)
    rationale: Annotated[str, StringConstraints(min_length=1, max_length=240)]

    @model_validator(mode="after")
    def validate_status(self) -> "ProtectedCoverageV2":
        present = bool(self.protected_fact_ids)
        if (self.status == "present") != present:
            raise ValueError("coverage status must match protected facts")
        if self.status == "missing" and (
            self.number_ids or self.source_slide_ids or self.minimum_planner_slide_mentions
        ):
            raise ValueError("missing coverage cannot fabricate evidence or planner obligations")
        if self.status == "present" and self.minimum_planner_slide_mentions < 1:
            raise ValueError("present protected coverage requires a planner obligation")
        return self


class NormalizedSourcePackageV2(FrozenModel):
    schema_version: Literal["instant-deck-source-package.v2"] = SOURCE_PACKAGE_VERSION_V2
    package_id: Annotated[str, StringConstraints(pattern=r"^srcpkgv2_[a-f0-9]{16}$")]
    source_checksum: Sha256
    source_package_v1_sha256: Sha256 | None
    production_context_sha256: Sha256 | None = None
    source_file: SourceFileIdentity
    source_slides: tuple[SourceSlideRecord, ...] = Field(min_length=1, max_length=500)
    source_references: tuple[SourceReference, ...] = Field(min_length=1)
    facts: tuple[MaterialFactV2, ...] = Field(min_length=1)
    claims: tuple[SourceClaimRecord, ...] = Field(min_length=1)
    numbers: tuple[SourceNumberRecord, ...]
    assets: tuple[SourceAssetRecordV2, ...]
    brand: SourceBackedBrandMetadataV2
    protected_coverage: tuple[ProtectedCoverageV2, ...] = Field(min_length=4, max_length=4)
    debris_exclusions: tuple[DebrisExclusion, ...]
    missing_evidence: tuple[MissingEvidenceRecord, ...]
    conflicts: tuple[SourceConflictRecord, ...]
    embedding_policy: SourceEmbeddingPolicy
    wordmark_rasterizer_version: Literal[
        "instant-deck-wordmark-rasterizer.v1"
    ] = WORDMARK_RASTERIZER_VERSION
    materiality_policy_version: Literal[
        "instant-deck-materiality-policy.v1"
    ] = MATERIALITY_POLICY_VERSION
    asset_role_policy_version: Literal[
        "instant-deck-asset-role-policy.v1"
    ] = ASSET_ROLE_POLICY_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> "NormalizedSourcePackageV2":
        if (self.source_package_v1_sha256 is None) == (self.production_context_sha256 is None):
            raise ValueError("Source package requires exactly one authentic parent identity")
        reference_id_list = [row.reference_id for row in self.source_references]
        source_id_list = [row.source_slide_id for row in self.source_slides]
        fact_id_list = [row.fact_id for row in self.facts]
        claim_id_list = [row.claim_id for row in self.claims]
        number_id_list = [row.number_id for row in self.numbers]
        reference_ids = set(reference_id_list)
        source_ids = set(source_id_list)
        fact_ids = set(fact_id_list)
        claim_ids = set(claim_id_list)
        number_ids = set(number_id_list)
        asset_ids = [row.asset_id for row in self.assets]
        for label, values in (
            ("source reference", reference_id_list),
            ("source slide", source_id_list),
            ("fact", fact_id_list),
            ("claim", claim_id_list),
            ("number", number_id_list),
            ("source asset", asset_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} ID")
        if self.package_id != f"srcpkgv2_{self.source_checksum[:16]}":
            raise ValueError("package ID must be derived from the source checksum")
        if [row.position for row in self.source_slides] != list(
            range(1, len(self.source_slides) + 1)
        ):
            raise ValueError("source slides must have contiguous ordered positions")
        if any(row.source_slide_id not in source_ids for row in self.source_references):
            raise ValueError("source reference points to an unknown source slide")
        for row in self.claims:
            if not set(row.fact_ids) <= fact_ids or not set(
                row.source_reference_ids
            ) <= reference_ids:
                raise ValueError(f"unknown claim provenance: {row.claim_id}")
        for row in self.numbers:
            if not set(row.source_reference_ids) <= reference_ids:
                raise ValueError(f"unknown number provenance: {row.number_id}")
        for row in self.assets:
            if not set(row.source_reference_ids) <= reference_ids:
                raise ValueError(f"unknown asset provenance: {row.asset_id}")
            if row.source_document_sha256 != self.source_checksum:
                raise ValueError(f"cross-source asset is forbidden: {row.asset_id}")
        asset_id_set = set(asset_ids)
        for row in self.source_slides:
            if (
                not set(row.fact_ids) <= fact_ids
                or not set(row.claim_ids) <= claim_ids
                or not set(row.number_ids) <= number_ids
                or not set(row.asset_ids) <= asset_id_set
            ):
                raise ValueError(f"source slide has a dangling relationship: {row.source_slide_id}")
        brand_reference_ids = (
            set(self.brand.organization_source_reference_ids)
            | set(self.brand.product_source_reference_ids)
            | set(self.brand.audience_source_reference_ids)
            | set(self.brand.deck_type_source_reference_ids)
            | {reference for role in self.brand.roles for reference in role.source_reference_ids}
        )
        if not brand_reference_ids <= reference_ids:
            raise ValueError("brand metadata contains unknown provenance")
        categories = [row.category for row in self.protected_coverage]
        if set(categories) != set(ProtectedCoverageCategory) or len(categories) != 4:
            raise ValueError("protected coverage must contain each required category exactly once")
        for row in self.facts:
            if not set(row.source_reference_ids) <= reference_ids:
                raise ValueError(f"unknown fact provenance: {row.fact_id}")
        for row in self.protected_coverage:
            if not set(row.protected_fact_ids) <= fact_ids:
                raise ValueError(f"unknown protected fact: {row.category.value}")
            if not set(row.number_ids) <= number_ids:
                raise ValueError(f"unknown protected number: {row.category.value}")
            if not set(row.source_slide_ids) <= source_ids:
                raise ValueError(f"unknown protected source slide: {row.category.value}")
        planner_protected = {row.fact_id for row in self.facts if row.planner_protected}
        coverage_protected = {
            fact_id for row in self.protected_coverage for fact_id in row.protected_fact_ids
        }
        if planner_protected != coverage_protected:
            raise ValueError("planner-protected facts and protected coverage must match exactly")
        if self.brand.wordmark_asset_id is not None:
            wordmark = next(
                (row for row in self.assets if row.asset_id == self.brand.wordmark_asset_id),
                None,
            )
            if wordmark is None or wordmark.semantic_role != AssetSemanticRole.WORDMARK:
                raise ValueError("brand wordmark must resolve to a wordmark asset")
        if (
            self.embedding_policy.scope != "request_data_only"
            or self.embedding_policy.global_knowledge_eligible is not False
            or self.embedding_policy.embedding_action != "none"
        ):
            raise ValueError("customer source must remain request-only and non-embedded")
        return self


@dataclass(frozen=True, slots=True)
class SourcePackageV2Bundle:
    package: NormalizedSourcePackageV2
    derived_asset_bytes: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        assets = {row.asset_id: row for row in self.package.assets}
        derived_ids = [asset_id for asset_id, _ in self.derived_asset_bytes]
        if len(derived_ids) != len(set(derived_ids)):
            raise SourcePackageV2Error("duplicate_derived_asset_bytes", ",".join(derived_ids))
        expected_derived_ids = {
            row.asset_id
            for row in self.package.assets
            if row.acquisition in {"vector_wordmark_rasterized", "page_region_rasterized"}
        }
        if set(derived_ids) != expected_derived_ids:
            raise SourcePackageV2Error(
                "derived_asset_set_mismatch",
                ",".join(sorted(expected_derived_ids - set(derived_ids))),
            )
        for asset_id, payload in self.derived_asset_bytes:
            asset = assets.get(asset_id)
            if asset is None:
                raise SourcePackageV2Error("unknown_derived_asset", asset_id)
            if sha256(payload).hexdigest() != asset.byte_sha256:
                raise SourcePackageV2Error("derived_asset_hash_mismatch", asset_id)

    def bytes_by_asset_id(self) -> dict[str, bytes]:
        return dict(self.derived_asset_bytes)


_FINANCIAL = re.compile(
    r"(?:€|\beur\b|revenue|funding|fund\b|investment|investor|asset(?:s)? under management|"
    r"\bspv\b|ticket|share|economics|capital|financial|angel checks?|\bchecks?\b)",
    re.IGNORECASE,
)
_TRACTION = re.compile(
    r"(?:\btraction\b|"
    r"(?:\d[\d.,+]*|\d+\s*(?:k|m|million))\s*"
    r"(?:registered\s+)?(?:houses?|famil(?:y|ies)|workshops?|consultations?|events?|"
    r"clients?|participants?|members?)\b|"
    r"(?:\d[\d.,+]*|\d+\s*(?:k|m|million))\s+projects?\s+"
    r"(?:started|completed|registered|supported)\b|"
    r"(?:registered\s+)?(?:houses?|famil(?:y|ies)|workshops?|consultations?|events?|"
    r"clients?|participants?|members?)"
    r"\s*(?:registered|served|supported|completed|started|to\s+date|so\s+far)\s*\d)",
    re.IGNORECASE,
)
_FOUNDER = re.compile(
    r"(?:\bthe founder\b|\bco-founder\b|\bfounded by\b|\bfounder\s*[:—-]|credential|"
    r"\bleadership\b|investment committee|track record|published author|\buniversity\b|"
    r"executive programme|\baward\b)",
    re.IGNORECASE,
)
_ASK = re.compile(
    r"(?:\bask\b|seeking|looking for|raise|funding sought|investment opportunity|invest with|"
    r"partner with|capital required|commitment|angel checks?)",
    re.IGNORECASE,
)


def _coverage_categories(text: str, kind: str) -> tuple[ProtectedCoverageCategory, ...]:
    categories: set[ProtectedCoverageCategory] = set()
    if kind == "financial" or _FINANCIAL.search(text):
        categories.add(ProtectedCoverageCategory.FINANCIAL)
    if _TRACTION.search(text):
        categories.add(ProtectedCoverageCategory.TRACTION)
    if kind == "team" or _FOUNDER.search(text):
        categories.add(ProtectedCoverageCategory.FOUNDER)
    if _ASK.search(text):
        categories.add(ProtectedCoverageCategory.ASK)
    return tuple(sorted(categories, key=lambda row: row.value))


def _material_fact(
    fact,
    *,
    number_reference_ids: set[str],
) -> MaterialFactV2:
    categories = _coverage_categories(fact.text, fact.kind)
    reasons: list[str] = ["source-marked-material" if fact.material else "source-contextual"]
    score = 35 if fact.material else 10
    kind_bonus = {
        "financial": 25,
        "team": 20,
        "metric": 20,
        "partnership": 12,
        "product": 10,
        "identity": 8,
    }.get(fact.kind, 0)
    if kind_bonus:
        score += kind_bonus
        reasons.append(f"{fact.kind}-kind")
    if set(fact.source_reference_ids) & number_reference_ids:
        score += 20
        reasons.append("exact-number-evidence")
    if categories:
        score += min(30, 15 + 5 * len(categories))
        reasons.append("protected-commercial-coverage")
    if len(fact.text) <= 120:
        score += 5
        reasons.append("presentation-ready-specificity")
    score = min(100, score)
    band = (
        MaterialityBand.CRITICAL
        if score >= 80
        else MaterialityBand.HIGH
        if score >= 65
        else MaterialityBand.SUPPORTING
        if score >= 45
        else MaterialityBand.CONTEXTUAL
    )
    return MaterialFactV2(
        fact_id=fact.fact_id,
        kind=fact.kind,
        text=fact.text,
        material=fact.material,
        materiality_score=score,
        materiality_band=band,
        coverage_categories=categories,
        planner_protected=False,
        score_reasons=tuple(reasons),
        source_reference_ids=tuple(fact.source_reference_ids),
    )


def _reference_page_maps(package: NormalizedSourcePackage) -> tuple[dict[str, int], dict[str, str]]:
    slide_pages = {row.source_slide_id: row.source_page_number for row in package.source_slides}
    reference_pages = {
        row.reference_id: slide_pages[row.source_slide_id]
        for row in package.source_references
        if row.source_slide_id in slide_pages
    }
    reference_slides = {
        row.reference_id: row.source_slide_id for row in package.source_references
    }
    return reference_pages, reference_slides


def _asset_context(package: NormalizedSourcePackage, source_page: int) -> str:
    source_slide = next(
        (row for row in package.source_slides if row.source_page_number == source_page),
        None,
    )
    if source_slide is None:
        return ""
    facts = {row.fact_id: row.text for row in package.facts}
    return " ".join(
        [source_slide.title, source_slide.normalized_text]
        + [facts.get(fact_id, "") for fact_id in source_slide.fact_ids]
    ).casefold()


def _classify_existing_asset(
    package: NormalizedSourcePackage,
    asset,
    *,
    source_page: int,
) -> tuple[AssetSemanticRole, float, tuple[str, ...]]:
    context = _asset_context(package, source_page)
    alt = asset.alt_text.casefold()
    ratio = asset.width / asset.height
    if asset.asset_type == "logo" or "literal logo" in alt:
        return AssetSemanticRole.LITERAL_LOGO, 0.98, ("source-declared-logo",)
    if "wordmark" in alt:
        return AssetSemanticRole.WORDMARK, 0.98, ("source-declared-wordmark",)
    if asset.asset_type == "diagram":
        return AssetSemanticRole.DIAGRAM, 0.96, ("source-declared-diagram",)
    if asset.asset_type == "portrait" or (
        _FOUNDER.search(context) and ratio <= 1.15
    ):
        return AssetSemanticRole.FOUNDER_PORTRAIT, 0.9, (
            "founder-context",
            "portrait-compatible-ratio",
        )
    if re.search(r"workshop|event|community|consultation", context):
        return AssetSemanticRole.EVENT_PHOTOGRAPHY, 0.82, ("event-or-workshop-context",)
    if re.search(r"institute|programme|program\b|academy|education", context):
        return AssetSemanticRole.PROGRAMME_IMAGERY, 0.82, ("programme-context",)
    if source_page == 1 and asset.mime_type in {"image/png", "image/jpeg", "image/webp"}:
        return AssetSemanticRole.BRAND_ARCHITECTURE, 0.8, (
            "cover-source",
            "photographic-brand-context",
        )
    if package.brand.logo_asset_id == asset.asset_id and asset.asset_type != "logo":
        return AssetSemanticRole.BRAND_SYMBOL, 0.65, (
            "legacy-brand-candidate",
            "not-source-declared-logo",
        )
    return AssetSemanticRole.EVIDENCE_IMAGE, 0.6, ("source-image-without-stronger-role-evidence",)


def _signature_colour(package: NormalizedSourcePackage) -> str:
    preferred = next(
        (row.colour for row in package.brand.roles if "signature" in row.role_id),
        None,
    )
    if preferred is not None:
        return preferred
    return package.brand.roles[-1].colour


def _wordmark_spans(page, organization_name: str) -> tuple[list[dict], float]:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z0-9]+", organization_name)]
    spans: list[dict] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = " ".join(str(span.get("text") or "").split()).casefold()
                covered = {token for token in tokens if token in text}
                if covered:
                    spans.append({**span, "covered_tokens": covered})
    if not spans:
        return [], 0.0
    maximum_size = max(float(row.get("size") or 0) for row in spans)
    dominant = [
        row for row in spans if float(row.get("size") or 0) >= maximum_size * 0.94
    ]
    covered = {token for row in dominant for token in row["covered_tokens"]}
    if not set(tokens) <= covered:
        return [], 0.0
    return dominant, maximum_size


def _select_wordmark_region(document, organization_name: str):
    candidates: list[tuple[float, int, object, tuple[object, ...]]] = []
    for page_index in range(document.page_count):
        page = document[page_index]
        spans, maximum_size = _wordmark_spans(page, organization_name)
        if not spans:
            continue
        rectangles = [page.rect & type(page.rect)(row["bbox"]) for row in spans]
        rectangles = [row for row in rectangles if not row.is_empty]
        if not rectangles:
            continue
        region = rectangles[0]
        for rectangle in rectangles[1:]:
            region |= rectangle
        if region.width <= 0 or region.height <= 0:
            continue
        coverage = region.get_area() / max(1.0, page.rect.get_area())
        if coverage > 0.8:
            continue
        candidates.append((maximum_size, page_index, region, tuple(rectangles)))
    if not candidates:
        raise SourcePackageV2Error(
            "wordmark_not_found",
            "organization text is not available as a bounded vector/text region",
        )
    maximum_size, page_index, region, rectangles = sorted(
        candidates,
        key=lambda row: (-row[0], row[1], row[2].get_area()),
    )[0]
    if maximum_size < 18:
        raise SourcePackageV2Error("wordmark_ambiguous", "largest organization mark is body scale")
    return page_index, region, rectangles


def _transparent_signature_raster(
    page,
    region,
    allowed_rectangles,
    signature_colour: str,
) -> tuple[bytes, str, int, int]:
    import fitz
    from PIL import Image, ImageChops, ImageDraw

    longest = max(region.width, region.height)
    scale = min(3.0, 1600.0 / max(1.0, longest))
    source_pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=region, alpha=False)
    source = Image.frombytes(
        "RGB",
        (source_pixmap.width, source_pixmap.height),
        source_pixmap.samples,
    )
    source_output = BytesIO()
    source.save(source_output, format="PNG", optimize=False, compress_level=9)
    source_region_hash = sha256(source_output.getvalue()).hexdigest()

    target = tuple(int(signature_colour[index : index + 2], 16) for index in (1, 3, 5))
    raw = source.tobytes()
    alpha = bytearray(len(raw) // 3)
    for source_index, alpha_index in zip(range(0, len(raw), 3), range(len(alpha))):
        red, green, blue = raw[source_index : source_index + 3]
        distance = max(abs(red - target[0]), abs(green - target[1]), abs(blue - target[2]))
        dominance = red - max(green, blue)
        value = max(0, min(255, 255 - distance * 5)) if distance <= 50 and dominance >= 45 else 0
        alpha[alpha_index] = value
    alpha_image = Image.frombytes("L", source.size, bytes(alpha))
    allowed = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(allowed)
    scale_x = source.width / region.width
    scale_y = source.height / region.height
    padding = max(2, round(max(source.size) * 0.004))
    for rectangle in allowed_rectangles:
        draw.rectangle(
            (
                max(0, round((rectangle.x0 - region.x0) * scale_x) - padding),
                max(0, round((rectangle.y0 - region.y0) * scale_y) - padding),
                min(source.width, round((rectangle.x1 - region.x0) * scale_x) + padding),
                min(source.height, round((rectangle.y1 - region.y0) * scale_y) + padding),
            ),
            fill=255,
        )
    alpha_image = ImageChops.multiply(alpha_image, allowed)
    alpha_bytes = alpha_image.tobytes()
    active_rows = [
        any(alpha_bytes[row * source.width : (row + 1) * source.width])
        for row in range(source.height)
    ]
    clusters: list[tuple[int, int]] = []
    start: int | None = None
    for row, active in enumerate([*active_rows, False]):
        if active and start is None:
            start = row
        elif not active and start is not None:
            clusters.append((start, row))
            start = None
    if clusters:
        minimum_height = max(8, round(source.height * 0.06))
        retained = [cluster for cluster in clusters if cluster[1] - cluster[0] >= minimum_height]
        if retained:
            row_mask = Image.new("L", source.size, 0)
            row_draw = ImageDraw.Draw(row_mask)
            for top, bottom in retained:
                row_draw.rectangle((0, top, source.width, bottom - 1), fill=255)
            alpha_image = ImageChops.multiply(alpha_image, row_mask)
    kept = sum(alpha_image.histogram()[1:])
    if kept < max(64, len(alpha) // 2000):
        raise SourcePackageV2Error(
            "wordmark_colour_mask_failed",
            "bounded organization region does not contain enough signature-colour ink",
        )
    rgba = source.convert("RGBA")
    rgba.putalpha(alpha_image)
    bbox = rgba.getbbox()
    if bbox is None:
        raise SourcePackageV2Error("wordmark_raster_empty", "wordmark alpha bounds are empty")
    padding = max(4, round(max(source.size) * 0.0125))
    crop = (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(rgba.width, bbox[2] + padding),
        min(rgba.height, bbox[3] + padding),
    )
    wordmark = rgba.crop(crop)
    output = BytesIO()
    wordmark.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue(), source_region_hash, wordmark.width, wordmark.height


def _rasterize_wordmark(
    source_pdf_bytes: bytes,
    package: NormalizedSourcePackage,
) -> tuple[SourceAssetRecordV2, bytes, SourceReference]:
    try:
        import fitz

        document = fitz.open(stream=source_pdf_bytes, filetype="pdf")
    except Exception as exc:  # pragma: no cover - library details vary
        raise SourcePackageV2Error("source_pdf_invalid", type(exc).__name__) from exc
    try:
        if document.page_count != package.source_file.page_count:
            raise SourcePackageV2Error(
                "source_page_count_mismatch",
                f"{document.page_count}!={package.source_file.page_count}",
            )
        page_index, region, wordmark_rectangles = _select_wordmark_region(
            document,
            package.brand.organization_name,
        )
        page = document[page_index]
        wordmark_bytes, source_region_hash, width, height = _transparent_signature_raster(
            page,
            region,
            wordmark_rectangles,
            _signature_colour(package),
        )
        page_number = page_index + 1
        asset_id = f"assetv2_s{page_number:02d}_wordmark"
        existing_reference_ids = {row.reference_id for row in package.source_references}
        reference_id = next(
            (
                f"ref_s{page_number:02d}_a{index:02d}"
                for index in range(99, 0, -1)
                if f"ref_s{page_number:02d}_a{index:02d}" not in existing_reference_ids
            ),
            None,
        )
        if reference_id is None:
            raise SourcePackageV2Error("wordmark_reference_exhausted", str(page_number))
        source_slide = next(
            row for row in package.source_slides if row.source_page_number == page_number
        )
        reference = SourceReference(
            reference_id=reference_id,
            source_slide_id=source_slide.source_slide_id,
            kind="asset",
            block_index=None,
            quoted_text=None,
        )
        normalized = NormalizedSourceRegionV2(
            left=round(region.x0 / page.rect.width, 8),
            top=round(region.y0 / page.rect.height, 8),
            right=round(region.x1 / page.rect.width, 8),
            bottom=round(region.y1 / page.rect.height, 8),
        )
        asset = SourceAssetRecordV2(
            asset_id=asset_id,
            semantic_role=AssetSemanticRole.WORDMARK,
            role_confidence=1.0,
            role_reasons=("organization-name-vector-region", "signature-colour-isolation"),
            acquisition="vector_wordmark_rasterized",
            mime_type="image/png",
            byte_sha256=sha256(wordmark_bytes).hexdigest(),
            width=width,
            height=height,
            alt_text=f"Source-derived {package.brand.organization_name} wordmark",
            source_document_sha256=package.source_checksum,
            source_page=page_number,
            source_region=normalized,
            source_region_sha256=source_region_hash,
            source_reference_ids=(reference_id,),
            derived_from_asset_id=None,
            required_for_planner=True,
        )
        return asset, wordmark_bytes, reference
    except StopIteration as exc:
        raise SourcePackageV2Error(
            "wordmark_source_slide_missing",
            "selected wordmark page is absent from source slides",
        ) from exc
    finally:
        document.close()


def _protected_coverage(
    facts: tuple[MaterialFactV2, ...],
    numbers: tuple[SourceNumberRecord, ...],
    references: tuple[SourceReference, ...],
    selected_fact_ids_by_category: dict[ProtectedCoverageCategory, tuple[str, ...]],
) -> tuple[ProtectedCoverageV2, ...]:
    reference_slides = {row.reference_id: row.source_slide_id for row in references}
    rows: list[ProtectedCoverageV2] = []
    for category in ProtectedCoverageCategory:
        protected = tuple(
            row
            for row in facts
            if row.fact_id in selected_fact_ids_by_category[category]
        )
        protected_refs = {
            reference for row in protected for reference in row.source_reference_ids
        }
        protected_numbers = tuple(
            sorted(
                row.number_id
                for row in numbers
                if set(row.source_reference_ids) & protected_refs
            )
        )
        source_slides = tuple(
            sorted(
                {
                    reference_slides[reference]
                    for reference in protected_refs
                    if reference in reference_slides
                }
            )
        )
        if protected:
            minimum = (
                2
                if category == ProtectedCoverageCategory.FINANCIAL
                and len(source_slides) >= 3
                else 1
            )
            rows.append(
                ProtectedCoverageV2(
                    category=category,
                    status="present",
                    protected_fact_ids=tuple(row.fact_id for row in protected),
                    number_ids=protected_numbers,
                    source_slide_ids=source_slides,
                    minimum_planner_slide_mentions=minimum,
                    rationale=(
                        "Planner must preserve this source-backed commercial category "
                        "during narrative compression."
                    ),
                )
            )
        else:
            rows.append(
                ProtectedCoverageV2(
                    category=category,
                    status="missing",
                    protected_fact_ids=(),
                    number_ids=(),
                    source_slide_ids=(),
                    minimum_planner_slide_mentions=0,
                    rationale=(
                        "The source package contains no sufficiently material evidence "
                        "for this category; do not invent it."
                    ),
                )
            )
    return tuple(rows)


_PROTECTED_FACT_LIMITS = {
    ProtectedCoverageCategory.FINANCIAL: 4,
    ProtectedCoverageCategory.TRACTION: 3,
    ProtectedCoverageCategory.FOUNDER: 2,
    ProtectedCoverageCategory.ASK: 2,
}


def _category_relevance(
    row: MaterialFactV2,
    category: ProtectedCoverageCategory,
) -> int:
    text = row.text.casefold()
    if category == ProtectedCoverageCategory.FINANCIAL:
        return (
            (30 if row.kind == "financial" else 0)
            + (
                15
                if re.search(r"\brevenue|\bfund\b|funding|capital|investment opportunity", text)
                else 0
            )
            - (
                20
                if re.search(r"university|programme|award|published author|credential", text)
                else 0
            )
        )
    if category == ProtectedCoverageCategory.TRACTION:
        return 30 if _TRACTION.search(text) else 0
    if category == ProtectedCoverageCategory.FOUNDER:
        return (
            (25 if row.kind == "team" else 0)
            + (
                20
                if re.search(r"co-founder|founded by|founder\s*[:—-]", text)
                else 0
            )
            + (
                15
                if re.search(
                    r"university|award|track record|published author|executive programme",
                    text,
                )
                else 0
            )
            - (15 if text.strip() == "the founder" else 0)
        )
    return (
        25
        if re.search(
            r"\bask\b|seeking|looking for|raise|investment opportunity|invest with|"
            r"capital required",
            text,
        )
        else 10
    )


def _protect_material_facts(
    facts: tuple[MaterialFactV2, ...],
) -> tuple[
    tuple[MaterialFactV2, ...],
    dict[ProtectedCoverageCategory, tuple[str, ...]],
]:
    selected: set[str] = set()
    selected_by_category: dict[ProtectedCoverageCategory, tuple[str, ...]] = {}
    for category in ProtectedCoverageCategory:
        candidates = [
            row
            for row in facts
            if row.material
            and row.materiality_score >= 60
            and category in row.coverage_categories
        ]
        candidates.sort(
            key=lambda row: (
                -_category_relevance(row, category),
                -row.materiality_score,
                "exact-number-evidence" not in row.score_reasons,
                row.fact_id,
            )
        )
        category_ids = tuple(
            row.fact_id for row in candidates[: _PROTECTED_FACT_LIMITS[category]]
        )
        selected_by_category[category] = category_ids
        selected.update(category_ids)
    protected_facts = tuple(
        row.model_copy(update={"planner_protected": row.fact_id in selected}) for row in facts
    )
    return protected_facts, selected_by_category


def build_source_package_v2(
    package_v1: NormalizedSourcePackage,
    *,
    source_pdf_bytes: bytes,
) -> SourcePackageV2Bundle:
    """Create deterministic Source Package v2 and request-bound derived bytes."""

    document_hash = sha256(source_pdf_bytes).hexdigest()
    if document_hash != package_v1.source_checksum:
        raise SourcePackageV2Error(
            "source_document_hash_mismatch",
            f"{document_hash}!={package_v1.source_checksum}",
        )
    if len(source_pdf_bytes) != package_v1.source_file.byte_size:
        raise SourcePackageV2Error(
            "source_document_size_mismatch",
            f"{len(source_pdf_bytes)}!={package_v1.source_file.byte_size}",
        )
    if package_v1.source_file.mime_type != "application/pdf":
        raise SourcePackageV2Error(
            "wordmark_rasterization_requires_pdf",
            package_v1.source_file.mime_type,
        )

    references = list(package_v1.source_references)
    reference_pages, _ = _reference_page_maps(package_v1)
    existing_assets: list[SourceAssetRecordV2] = []
    for asset in package_v1.assets:
        pages = {
            reference_pages[reference]
            for reference in asset.source_reference_ids
            if reference in reference_pages
        }
        if len(pages) != 1:
            raise SourcePackageV2Error(
                "asset_source_page_ambiguous",
                asset.asset_id,
            )
        source_page = pages.pop()
        role, confidence, reasons = _classify_existing_asset(
            package_v1,
            asset,
            source_page=source_page,
        )
        acquisition = "embedded_vector" if asset.mime_type == "image/svg+xml" else "embedded_raster"
        existing_assets.append(
            SourceAssetRecordV2(
                asset_id=asset.asset_id,
                semantic_role=role,
                role_confidence=confidence,
                role_reasons=reasons,
                acquisition=acquisition,
                mime_type=asset.mime_type,
                byte_sha256=asset.sha256,
                width=asset.width,
                height=asset.height,
                alt_text=asset.alt_text,
                source_document_sha256=package_v1.source_checksum,
                source_page=source_page,
                source_region=None,
                source_region_sha256=None,
                source_reference_ids=tuple(asset.source_reference_ids),
                derived_from_asset_id=None,
                required_for_planner=role
                in {
                    AssetSemanticRole.LITERAL_LOGO,
                    AssetSemanticRole.WORDMARK,
                    AssetSemanticRole.FOUNDER_PORTRAIT,
                },
            )
        )

    wordmark, wordmark_bytes, wordmark_reference = _rasterize_wordmark(
        source_pdf_bytes,
        package_v1,
    )
    references.append(wordmark_reference)
    source_slides = []
    for slide in package_v1.source_slides:
        if slide.source_page_number == wordmark.source_page:
            slide = slide.model_copy(
                update={"asset_ids": [*slide.asset_ids, wordmark.asset_id]}
            )
        source_slides.append(slide)

    number_reference_ids = {
        reference for row in package_v1.numbers for reference in row.source_reference_ids
    }
    facts, selected_fact_ids_by_category = _protect_material_facts(
        tuple(
            _material_fact(row, number_reference_ids=number_reference_ids)
            for row in package_v1.facts
        )
    )
    numbers = tuple(package_v1.numbers)
    references_tuple = tuple(references)
    coverage = _protected_coverage(
        facts,
        numbers,
        references_tuple,
        selected_fact_ids_by_category,
    )
    assets = tuple(sorted([*existing_assets, wordmark], key=lambda row: row.asset_id))
    literal_logo = next(
        (row.asset_id for row in assets if row.semantic_role == AssetSemanticRole.LITERAL_LOGO),
        None,
    )
    symbols = tuple(
        row.asset_id for row in assets if row.semantic_role == AssetSemanticRole.BRAND_SYMBOL
    )
    brand = SourceBackedBrandMetadataV2(
        organization_name=package_v1.brand.organization_name,
        organization_source_reference_ids=tuple(
            package_v1.brand.organization_source_reference_ids
        ),
        product_candidate=package_v1.brand.product_candidate,
        product_source_reference_ids=tuple(package_v1.brand.product_source_reference_ids),
        audience_candidate=package_v1.brand.audience_candidate,
        audience_source_reference_ids=tuple(package_v1.brand.audience_source_reference_ids),
        deck_type_candidate=package_v1.brand.deck_type_candidate,
        deck_type_source_reference_ids=tuple(package_v1.brand.deck_type_source_reference_ids),
        roles=tuple(package_v1.brand.roles),
        wordmark_asset_id=wordmark.asset_id,
        literal_logo_asset_id=literal_logo,
        brand_symbol_asset_ids=symbols,
    )
    package = NormalizedSourcePackageV2(
        package_id=f"srcpkgv2_{package_v1.source_checksum[:16]}",
        source_checksum=package_v1.source_checksum,
        source_package_v1_sha256=canonical_sha256(package_v1),
        source_file=package_v1.source_file,
        source_slides=tuple(source_slides),
        source_references=references_tuple,
        facts=facts,
        claims=tuple(package_v1.claims),
        numbers=numbers,
        assets=assets,
        brand=brand,
        protected_coverage=coverage,
        debris_exclusions=tuple(package_v1.debris_exclusions),
        missing_evidence=tuple(package_v1.missing_evidence),
        conflicts=tuple(package_v1.conflicts),
        embedding_policy=package_v1.embedding_policy,
    )
    return SourcePackageV2Bundle(
        package=package,
        derived_asset_bytes=((wordmark.asset_id, wordmark_bytes),),
    )
