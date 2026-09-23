from __future__ import annotations

import re
from dataclasses import dataclass


CLAIM_PATTERNS = {
    "market_size": re.compile(r"\b(TAM|SAM|SOM|market|opportunity|addressable)\b", re.I),
    "revenue_projection": re.compile(r"\b(ARR|MRR|revenue|sales|forecast|projection|growth)\b", re.I),
    "roi_claim": re.compile(r"\b(ROI|return on investment|payback|saving|savings|productivity|efficiency)\b", re.I),
    "unit_economics": re.compile(r"\b(CAC|LTV|gross margin|margin|churn|retention|payback|ARPU|ARPA|ACV)\b", re.I),
    "fundraising_ask": re.compile(r"\b(raise|fundraising|use of funds|runway|burn|milestone|round)\b", re.I),
    "valuation_claim": re.compile(r"\b(valuation|multiple|exit|return case|IRR|MOIC)\b", re.I),
}
NUMBER_PATTERN = re.compile(r"\d+(?:[,.]\d+)*(?:\.\d+)?\s*(?:k|m|bn|billion|million|thousand|percent|x)?", re.I)


@dataclass(frozen=True)
class ExtractedFinanceClaim:
    claim_type: str
    claim_text: str
    slide_id: str | None
    slide_title: str | None
    numbers: list[str]

    def to_dict(self) -> dict:
        return {
            "claimType": self.claim_type,
            "claimText": self.claim_text,
            "slideId": self.slide_id,
            "slideTitle": self.slide_title,
            "numbers": self.numbers,
        }


def _sentences(text: str) -> list[str]:
    clean = " ".join((text or "").split())
    if not clean:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", clean) if part.strip()]


def _claim_type(sentence: str) -> str | None:
    for claim_type, pattern in CLAIM_PATTERNS.items():
        if pattern.search(sentence):
            return claim_type
    if NUMBER_PATTERN.search(sentence):
        return "other"
    return None


def extract_financial_claims_from_slides(slides: list[dict], *, max_claims: int = 80) -> list[dict]:
    claims: list[ExtractedFinanceClaim] = []
    for slide in slides:
        slide_id = str(slide.get("id") or slide.get("slideId") or "") or None
        title = slide.get("title") or slide.get("slideTitle")
        text = "\n".join(str(value or "") for value in [title, slide.get("rawText"), slide.get("summary"), slide.get("narrativeNotes")])
        for sentence in _sentences(text):
            ctype = _claim_type(sentence)
            numbers = NUMBER_PATTERN.findall(sentence)
            if ctype and (numbers or ctype != "other"):
                claims.append(ExtractedFinanceClaim(ctype, sentence[:700], slide_id, str(title) if title else None, numbers[:8]))
                if len(claims) >= max_claims:
                    return [claim.to_dict() for claim in claims]
    return [claim.to_dict() for claim in claims]


def extract_financial_claims_from_deck_map(deck_map: dict | None) -> list[dict]:
    if not isinstance(deck_map, dict):
        return []
    slides = deck_map.get("slides") or deck_map.get("slideMap") or deck_map.get("sourceSlides") or []
    if not isinstance(slides, list):
        return []
    return extract_financial_claims_from_slides([slide for slide in slides if isinstance(slide, dict)])
