from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, HttpUrl

InterestLeadStatus = Literal["new", "reviewed", "invited", "converted_to_user", "archived"]


class InterestLeadCreate(BaseModel):
    email: EmailStr
    name: str | None = None
    company_name: str | None = None
    company_website_url: HttpUrl | None = None
    role_label: str | None = None
    use_case: str | None = None
    message: str | None = None
    source_page: str | None = None
    turnstileToken: str | None = None


class InterestLeadSummary(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    company_name: str | None = None
    company_website_url: HttpUrl | None = None
    role_label: str | None = None
    use_case: str | None = None
    message: str | None = None
    status: InterestLeadStatus
    source_page: str | None = None
    created_at: datetime
    updated_at: datetime


class PublicInterestResponse(BaseModel):
    ok: bool = True
    lead_id: str
    message: str
