"""Verify canonical page identity without any source thumbnail dependency."""

from sqlalchemy.orm import Session

from app.db.models import DeckSlide


def require_extracted_page_records(
    db: Session, *, deck_id: str, source_file_id: str,
    extraction_run_id: str, expected_page_count: int,
) -> list[DeckSlide]:
    pages = db.query(DeckSlide).filter(DeckSlide.deck_id == deck_id).order_by(DeckSlide.source_page_number).all()
    if expected_page_count <= 0 or len(pages) != expected_page_count:
        raise ValueError("Source publication requires every extracted page record.")
    if [page.source_page_number for page in pages] != list(range(1, expected_page_count + 1)):
        raise ValueError("Source publication requires contiguous source page markers.")
    if any(page.source_file_id != source_file_id or page.extraction_run_id != extraction_run_id for page in pages):
        raise ValueError("Source page records do not match the current extraction lineage.")
    return pages
