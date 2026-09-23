from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import InterestLead
from app.schemas.public_interest import InterestLeadCreate


def create_interest_lead(db: Session, payload: InterestLeadCreate) -> InterestLead:
    lead = InterestLead(
        id=f"lead_{uuid4().hex[:12]}",
        email=payload.email,
        name=payload.name,
        company_name=payload.company_name,
        company_website_url=str(payload.company_website_url) if payload.company_website_url else None,
        role_label=payload.role_label,
        use_case=payload.use_case,
        message=payload.message,
        status="new",
        source_page=payload.source_page or "home",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
