from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.brand_profile import (
    BrandExtractionStatusResponse,
    BrandPaletteSwatchPayload,
    DeckBrandProfilePayload,
    ExtractDeckBrandRouteResponse,
    DeckBrandProfileRouteResponse,
    UpdateDeckBrandProfileRequest,
)
from app.services.brand.brand_enrichment import enrich_brand_profile_after_extract
from app.services.brand.brand_extraction import (
    extract_deck_brand,
    get_deck_brand_asset_file,
    get_deck_brand_profile,
    update_deck_brand_profile,
)
from app.services.brand.brand_read_model import get_deck_brand_status
from app.services.brand.deterministic_swatches import (
    DETERMINISTIC_MAPPING_VERSION as SHARED_DETERMINISTIC_MAPPING_VERSION,
    with_deterministic_swatch_contract,
)

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["brand-extraction"])

# PRESERVED: route-level constant kept for any existing imports, but the shared
# implementation now lives in app.services.brand.deterministic_swatches.
DETERMINISTIC_MAPPING_VERSION = SHARED_DETERMINISTIC_MAPPING_VERSION

def _build_deterministic_swatches(profile: DeckBrandProfilePayload) -> list[BrandPaletteSwatchPayload]:
    swatches: list[BrandPaletteSwatchPayload] = []
    seen: set[str] = set()
    role_candidates = [
        ("Primary", profile.primaryColor),
        ("Secondary", profile.secondaryColor),
        ("Accent", profile.accentColor),
        ("Background", profile.backgroundColor),
        ("Text", profile.textColor),
    ]

    for label, value in role_candidates:
        if value is None:
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        swatches.append(BrandPaletteSwatchPayload(label=label, value=normalized))
        seen.add(normalized)

    for index, value in enumerate(profile.palette or []):
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        swatches.append(BrandPaletteSwatchPayload(label=f"Palette {index + 1}", value=normalized))
        seen.add(normalized)

    return swatches[:5]


def _with_deterministic_swatch_contract(profile: DeckBrandProfilePayload) -> DeckBrandProfilePayload:
    # DISABLED: route-local mutation was replaced by the shared brand service helper
    # so /brand/extract and /workflows/brand-extraction cannot drift apart again.
    # swatches = _build_deterministic_swatches(profile)
    # swatch_payload = [swatch.model_dump() for swatch in swatches]
    # raw_evidence = dict(profile.rawEvidence or {})
    # raw_evidence.setdefault("deterministicSwatches", swatch_payload)
    # raw_evidence.setdefault("deterministicMappingVersion", DETERMINISTIC_MAPPING_VERSION)
    # profile.deterministicSwatches = swatches
    # profile.deterministicMappingVersion = DETERMINISTIC_MAPPING_VERSION
    # profile.rawEvidence = raw_evidence
    # return profile
    return with_deterministic_swatch_contract(profile)


@router.post("/{deck_id}/brand/extract", response_model=ExtractDeckBrandRouteResponse)
async def deck_brand_extract(
    deck_id: str,
    companyUrl: str | None = Form(default=None),
    logoFile: UploadFile | None = File(default=None),
    brandGuidelinesFile: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtractDeckBrandRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        profile = await extract_deck_brand(db, deck_id, companyUrl, logoFile, brandGuidelinesFile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")

    try:
        # FIX 2: enrichment failures were silently swallowed, leaving profiles without
        # fonts, card swatches, or remote logos. Now we log the error so it surfaces.
        enrich_brand_profile_after_extract(db, deck_id)
        enriched_profile = get_deck_brand_profile(db, deck_id)
        if enriched_profile is not None:
            profile = enriched_profile
    except Exception as enrichment_error:
        # DISABLED: silent db.rollback() with no logging. Now we log the exception
        # so operators can see what went wrong, then still rollback to keep the session usable.
        db.rollback()
        logger.exception(
            "Brand enrichment failed for deck %s after successful extraction: %s",
            deck_id,
            enrichment_error,
        )

    profile = _with_deterministic_swatch_contract(profile)
    return ExtractDeckBrandRouteResponse(
        brandProfileId=profile.id,
        status="completed" if profile.status == "ready" else profile.status,
        brandProfile=profile,
    )


@router.get("/{deck_id}/brand/status", response_model=BrandExtractionStatusResponse)
def deck_brand_status(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandExtractionStatusResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    status_payload = get_deck_brand_status(db, deck_id)
    if status_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    if status_payload.brandProfile is not None:
        status_payload.brandProfile = _with_deterministic_swatch_contract(status_payload.brandProfile)
    return status_payload


@router.get("/{deck_id}/brand-assets/{asset_id}")
def deck_brand_asset(
    deck_id: str,
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    asset_file = get_deck_brand_asset_file(db, deck_id, asset_id)
    if asset_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand asset not found")

    path, media_type = asset_file
    return FileResponse(path, media_type=media_type)


@router.get("/{deck_id}/brand-profile", response_model=DeckBrandProfileRouteResponse)
def deck_brand_profile(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckBrandProfileRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    profile = get_deck_brand_profile(db, deck_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")
    profile = _with_deterministic_swatch_contract(profile)
    return DeckBrandProfileRouteResponse(deckId=deck_id, brandProfile=profile)


@router.patch("/{deck_id}/brand-profile", response_model=DeckBrandProfileRouteResponse)
def deck_brand_profile_patch(
    deck_id: str,
    payload: UpdateDeckBrandProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckBrandProfileRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    profile = update_deck_brand_profile(db, deck_id, payload.model_dump(exclude_unset=True))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand profile not found")
    profile = _with_deterministic_swatch_contract(profile)
    return DeckBrandProfileRouteResponse(deckId=deck_id, brandProfile=profile)
