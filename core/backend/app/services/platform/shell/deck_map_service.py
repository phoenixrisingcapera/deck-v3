from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AnalysisFinding,
    BlockClassification,
    Deck,
    DeckSlide,
    DeckSlideBlock,
    Workspace,
)
from app.schemas.deck_map import (
    DeckMapClassificationSummary,
    DeckMapCompanyBasics,
    DeckMapFindingsSummary,
    DeckMapResponse,
    DeckMapSlideDistribution,
    DeckMapSlideOverview,
)


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.workspace),
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def get_deck_map(db: Session, deck_id: str) -> DeckMapResponse | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None

    slides = sorted(deck.slides, key=lambda s: s.slide_index)
    blocks = [b for s in slides for b in sorted(s.blocks, key=lambda b: b.block_index)]
    block_ids = [b.id for b in blocks]

    classifications: list[BlockClassification] = []
    if block_ids:
        classifications = (
            db.query(BlockClassification)
            .filter(BlockClassification.block_id.in_(block_ids))
            .order_by(BlockClassification.confidence.desc())
            .all()
        )

    findings: list[AnalysisFinding] = (
        db.query(AnalysisFinding)
        .filter(AnalysisFinding.deck_id == deck_id)
        .all()
    )

    company = DeckMapCompanyBasics(
        companyName=deck.title,
        audience=deck.audience,
        purpose=deck.purpose,
        summary=deck.summary,
    )

    role_counts: dict[str, int] = defaultdict(int)
    for slide in slides:
        role_counts[slide.role or "unknown"] += 1
    by_role = sorted(
        (DeckMapSlideDistribution(role=role, count=count) for role, count in role_counts.items()),
        key=lambda d: d.count,
        reverse=True,
    )
    slide_overview = DeckMapSlideOverview(totalSlides=len(slides), byRole=by_role)

    tag_to_slides: dict[str, set[str]] = defaultdict(set)
    block_id_to_slide: dict[str, str] = {}
    for slide in slides:
        for block in slide.blocks:
            block_id_to_slide[block.id] = slide.id

    tag_counts: dict[str, int] = defaultdict(int)
    for c in classifications:
        tag_counts[c.semantic_tag] += 1
        slide_id = block_id_to_slide.get(c.block_id)
        if slide_id:
            tag_to_slides[c.semantic_tag].add(slide_id)

    class_summaries = sorted(
        (
            DeckMapClassificationSummary(
                semanticTag=tag,
                count=count,
                sampleSlides=list(tag_to_slides[tag])[:3],
            )
            for tag, count in tag_counts.items()
        ),
        key=lambda s: s.count,
        reverse=True,
    )

    finding_buckets: dict[tuple[str, str], int] = defaultdict(int)
    for f in findings:
        finding_buckets[(f.severity, f.category)] += 1
    finding_summaries = sorted(
        (
            DeckMapFindingsSummary(severity=sev, category=cat, count=cnt)
            for (sev, cat), cnt in finding_buckets.items()
        ),
        key=lambda s: s.count,
        reverse=True,
    )

    return DeckMapResponse(
        deckId=deck_id,
        company=company,
        slideOverview=slide_overview,
        classifications=class_summaries,
        findings=finding_summaries,
    )
