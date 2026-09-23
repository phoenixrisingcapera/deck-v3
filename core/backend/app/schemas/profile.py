from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserProfileSummary(BaseModel):
    id: str
    userId: str
    displayName: str | None = None
    headline: str | None = None
    companyName: str | None = None
    jobTitle: str | None = None
    department: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str | None = None
    preferredLanguage: str | None = None
    workEmail: EmailStr | None = None
    linkedinProfileUrl: str | None = None
    skills: list[str] = []
    education: list[dict] = []
    certifications: list[dict] = []
    profileSource: dict = {}
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class UserProfileUpdateRequest(BaseModel):
    displayName: str | None = None
    headline: str | None = None
    companyName: str | None = None
    jobTitle: str | None = None
    department: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str | None = None
    preferredLanguage: str | None = None
    workEmail: EmailStr | None = None
    linkedinProfileUrl: str | None = None
    skills: list[str] | None = None
    education: list[dict] | None = None
    certifications: list[dict] | None = None
    profileSource: dict | None = None


class UserProfileRouteResponse(BaseModel):
    profile: UserProfileSummary
