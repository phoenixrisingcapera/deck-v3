"""Optional text-level brand extraction agent.

This reads slide text for brand signals. It does not replace the working
`brand_extraction` workflow, which owns persisted DeckBrandProfile records.

This agent is called during deck processing to extract brand information
from slide content when no explicit brand profile has been provided.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

# System prompt that instructs the LLM on what brand information to extract
# from slide content. The LLM should return structured JSON with brand identity.
BRAND_AGENT_SYSTEM_PROMPT = """You are a brand identity analyst. Analyze slide content and extract brand information.

Extract:
1. BRAND_NAME — The company or product brand name
2. TAGLINE — Any tagline or slogan used
3. BRAND_VOICE — The tone and voice (professional, innovative, disruptive, etc.)
4. VISUAL_STYLE — Design style descriptions (minimalist, bold, corporate, etc.)
5. COLOR_HINTS — Color schemes mentioned or strongly implied
6. LOGO_DESCRIPTION — Description of any logo mentioned
7. BRAND_VALUES — Core values expressed (innovation, sustainability, customer-first, etc.)

Return JSON:
{
  "brandName": "string | null",
  "tagline": "string | null",
  "brandVoice": ["string"],
  "visualStyle": ["string"],
  "colorHints": ["string"],
  "logoDescription": "string | null",
  "brandValues": ["string"],
  "brandMaturity": "early_stage|growing|established|market_leader",
  "confidence": 0.0-1.0
}"""


def run_brand_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Extract brand information from slide content using LLM.
    
    This is the main entry point for the brand agent. It:
    1. Filters slides to find brand-relevant content
    2. Extracts text from those slides
    3. Sends to LLM for brand analysis
    4. Returns structured brand information or fallback
    
    Args:
        slides_data: List of slide dictionaries with 'title', 'rawText', 'narrativeNotes'
        provider_config: Optional LLM provider configuration (model, api_key, etc.)
    
    Returns:
        Dictionary with 'status' and 'brand' keys:
        - status: 'completed', 'skipped', or 'fallback'
        - brand: Extracted brand information or fallback brand data
        
        Returns None if extraction fails completely.
    """
    # Skip if no slides provided
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    # Find slides that contain brand-related keywords
    brand_slides = _find_brand_relevant_slides(slides_data)
    
    # Extract all text from brand-relevant slides
    # Combine raw text (slide content) with narrative notes (speaker notes)
    all_text = " ".join(
        s.get("rawText", "") + " " + s.get("narrativeNotes", "")
        for s in brand_slides
    ).strip()

    # If no text found in brand-relevant slides, skip extraction
    if not all_text:
        return {"status": "skipped", "reason": "no brand-relevant text"}

    # Build user prompt with slide context for the LLM
    user_prompt = f"""Extract brand identity information from this slide deck.

Brand-relevant slides: {len(brand_slides)} out of {len(slides_data)} total.

Slide titles examined: {[s.get('title', '') for s in brand_slides]}

Full text:
{all_text[:4000]}

Return JSON with extracted brand info."""

    # Call LLM to extract brand information
    # complete_json_with_ai_provider handles JSON parsing and error recovery
    result = complete_json_with_ai_provider(
        provider_config=provider_config,
        system=BRAND_AGENT_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=2000,
    )

    # If LLM extraction failed, return fallback brand data
    # Fallback extracts minimal info from the first word of text
    if result is None:
        return {"status": "fallback", "brand": _fallback_brand(all_text)}

    # Return successfully extracted brand information
    return {"status": "completed", "brand": result}


# Keywords that indicate brand-relevant content in slides
# Used to filter slides before sending to LLM
BRAND_KEYWORDS = [
    "brand", "logo", "tagline", "slogan", "mission", "vision",
    "about us", "who we are", "identity", "branding",
    "color", "palette", "design", "style guide",
]


def _find_brand_relevant_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter slides to find those containing brand-related content.
    
    Searches slide titles and text for brand keywords. If no slides
    match the keywords, returns the first slide as a fallback.
    
    Args:
        slides: List of slide dictionaries
    
    Returns:
        List of brand-relevant slides (at least one if input is non-empty)
    """
    relevant = []
    
    # Check each slide for brand keywords
    for s in slides:
        # Combine slide text and narrative notes, convert to lowercase
        text = ((s.get("rawText") or "") + " " + (s.get("narrativeNotes") or "")).lower()
        # Get slide title, convert to lowercase
        title = (s.get("title") or "").lower()
        
        # Check if any brand keyword appears in title or text
        if any(kw in f"{title} {text}" for kw in BRAND_KEYWORDS):
            relevant.append(s)
    
    # If no brand-relevant slides found, use first slide as fallback
    # This ensures we always have at least one slide to analyze
    if not relevant and slides:
        relevant.append(slides[0])
    
    return relevant


def _fallback_brand(text: str) -> dict[str, Any]:
    """Generate minimal fallback brand data when LLM extraction fails.
    
    Extracts the first word as brand name and sets all other fields
    to empty/default values. Used when LLM call fails or returns None.
    
    Args:
        text: Raw text from slides (used to extract brand name)
    
    Returns:
        Dictionary with minimal brand information:
        - brandName: First word from text (or None if no text)
        - All other fields: Empty lists or None
        - confidence: 0.2 (low confidence indicator)
    """
    # Split text into words
    words = text.split()
    
    # Use first word as brand name, or None if no words
    name = words[0] if words else None
    
    # Return minimal brand structure with low confidence
    return {
        "brandName": name,
        "tagline": None,
        "brandVoice": [],
        "visualStyle": [],
        "colorHints": [],
        "logoDescription": None,
        "brandValues": [],
        "brandMaturity": "early_stage",
        "confidence": 0.2,
    }
