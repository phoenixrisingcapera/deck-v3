"""Brand extraction spine service.

Owns brand profile assembly for the source pipeline. It should prefer website
signals when available, fall back to deterministic deck-derived brand colors,
and allow optional enrichment to improve the resulting profile without owning
workflow readiness.
"""

from __future__ import annotations

import asyncio
import logging
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CompanyProfile, Deck, DeckBrandAsset, DeckBrandProfile, DeckInputSource, DeckSlide
from app.services.brand.brand_enrichment import enrich_brand_profile_after_extract
from app.services.brand.brand_extraction import extract_deck_brand
from app.services.brand.brand_profile_persistence import upsert_brand_profile
# The extractor package is the active home for source-analysis agents. The
# legacy copy remains available for historical reference only.
from app.agents.extractors.brand_agent import run_brand_agent

logger = logging.getLogger(__name__)
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def run_brand_extraction_for_deck(
    db: Session,
    deck: Deck,
    *,
    company_profile: CompanyProfile,
) -> DeckBrandProfile:
    """Extract brand profile for a deck using URL, logo, and slide content analysis.
    
    This function orchestrates the complete brand extraction workflow:
    1. Query input sources (website URLs, logos, brand guidelines)
    2. Query brand assets (uploaded files)
    3. Extract brand profile from URL/logo using deterministic methods
    4. Optionally enhance with LLM-based slide content analysis
    5. Enrich the profile with additional metadata
    6. Return the complete brand profile
    
    Args:
        db: Database session
        deck: Deck to extract brand for
        company_profile: Company profile to associate with brand
    
    Returns:
        DeckBrandProfile with extracted brand information
    """
    # Query all input sources for this deck (website URLs, logos, etc.)
    input_sources = (
        db.query(DeckInputSource)
        .filter(DeckInputSource.deck_id == deck.id)
        .order_by(DeckInputSource.created_at.asc())
        .all()
    )
    
    # Query all brand assets (uploaded logo files, brand guidelines)
    brand_assets = (
        db.query(DeckBrandAsset)
        .filter(DeckBrandAsset.deck_id == deck.id)
        .order_by(DeckBrandAsset.created_at.asc())
        .all()
    )
    
    # Extract brand profile using deterministic methods (URL scraping, logo analysis)
    # This creates or updates the DeckBrandProfile record
    profile = upsert_brand_profile(
        db,
        deck,
        company_profile,
        input_sources,
        brand_assets,
        deck.audience or "general audience",
        deck.purpose or "smart deck generation",
    )
    db.flush()

    # Reuse the canonical deterministic visual/font extractor after source
    # slides and blocks exist. It owns profile precedence and persistence, and
    # accepts absent URL/logo/guidelines. Do not call this function recursively
    # or introduce a second provider path here.
    asyncio.run(
        extract_deck_brand(
            db,
            deck.id,
            company_url=None,
            logo_file=None,
            brand_guidelines_file=None,
        )
    )
    db.refresh(profile)
    
    # The beta designer receives one application-owned brand snapshot. Do not
    # run a second LLM that infers colors/identity and merges a competing brand.
    # Retain the optional legacy enrichment for historical non-beta workflows.
    if not settings.instant_html_llm_first_beta:
        _enhance_brand_profile_with_slide_analysis(db, deck, profile)
    
    # Enrich the profile with additional metadata (typography, remote logo download, etc.)
    enrich_brand_profile_after_extract(db, deck.id)
    db.refresh(profile)
    return profile


def _enhance_brand_profile_with_slide_analysis(
    db: Session,
    deck: Deck,
    profile: DeckBrandProfile,
) -> None:
    """Enhance brand profile with LLM-based analysis of slide content.
    
    This function:
    1. Queries all slides for the deck
    2. Extracts text content from slides
    3. Calls the brand agent to analyze slide content
    4. Merges agent results into the brand profile's branding_json
    
    The agent provides complementary brand signals (brand voice, values, etc.)
    that deterministic URL/logo extraction cannot capture.
    
    Args:
        db: Database session
        deck: Deck to analyze
        profile: Brand profile to enhance
    """
    # Query all slides for this deck
    slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck.id)
        .order_by(DeckSlide.slide_index.asc())
        .all()
    )
    
    # Skip if no slides found
    if not slides:
        return
    
    # Build slide data for the brand agent
    # Extract title, raw text, and narrative notes from each slide
    slides_data = []
    for slide in slides:
        slide_dict = {
            "title": slide.title or "",
            "rawText": slide.raw_text or "",
            "narrativeNotes": slide.narrative_notes or "",
        }
        slides_data.append(slide_dict)
    
    # Call the optional brand agent best-effort. Deterministic brand extraction
    # must remain valid even when the LLM provider is unavailable or malformed.
    # PREVIOUS: agent_result = run_brand_agent(slides_data)
    try:
        agent_result = run_brand_agent(slides_data)
    except Exception:
        logger.exception("brand_agent_enrichment_failed", extra={"deck_id": deck.id})
        return
    
    # If agent returned results, merge them into the brand profile
    if agent_result and not isinstance(agent_result, dict):
        logger.warning("brand_agent_enrichment_ignored_malformed_result", extra={"deck_id": deck.id})
        return

    if agent_result and agent_result.get("status") in ("completed", "fallback"):
        brand_data = agent_result.get("brand", {})
        if not isinstance(brand_data, dict):
            logger.warning("brand_agent_enrichment_ignored_malformed_brand", extra={"deck_id": deck.id})
            return
        
        # Merge agent results into branding_json
        # branding_json contains the complete brand context for LLM generation
        branding_json = profile.branding_json or {}
        
        # Add agent-extracted brand signals
        if brand_data.get("brandName") and not branding_json.get("companyName"):
            branding_json["companyName"] = brand_data["brandName"]
        
        if brand_data.get("tagline"):
            branding_json["tagline"] = brand_data["tagline"]
        
        brand_voice = _string_list(brand_data.get("brandVoice"))
        if brand_voice:
            branding_json["brandVoice"] = brand_voice

        visual_style = _string_list(brand_data.get("visualStyle"))
        if visual_style:
            branding_json["visualStyle"] = visual_style

        brand_values = _string_list(brand_data.get("brandValues"))
        if brand_values:
            branding_json["brandValues"] = brand_values
        
        if brand_data.get("colorHints"):
            # Merge color hints with existing palette
            colors = branding_json.get("colors") if isinstance(branding_json.get("colors"), dict) else {}
            existing_palette = colors.get("palette", [])
            branding_json["colors"] = colors
            branding_json["colors"].setdefault("palette", [])
            # DISABLED: raw LLM color hints can contain labels like "deep blue".
            # Reason: palette consumers expect valid hex colours, so hints must be filtered.
            # branding_json["colors"]["palette"].extend(brand_data["colorHints"])
            branding_json["colors"]["palette"] = _merge_hex_palette(existing_palette, brand_data["colorHints"])
        
        # Store agent confidence and source
        branding_json["agentConfidence"] = brand_data.get("confidence", 0.0)
        branding_json["agentSource"] = "slide_content_analysis"
        
        # Update profile
        profile.branding_json = branding_json
        db.add(profile)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _merge_hex_palette(existing_palette: list | None, color_hints: list | None) -> list[str]:
    """Merge only valid hex colours returned by optional LLM enrichment."""

    merged: list[str] = []
    for value in [*(existing_palette or []), *(color_hints or [])]:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not HEX_COLOR_RE.fullmatch(candidate):
            continue
        normalized = candidate.upper()
        if normalized not in merged:
            merged.append(normalized)
    return merged


__all__ = ["run_brand_extraction_for_deck"]
