from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import User, UserProfile


def _serialize_profile(profile: UserProfile) -> dict:
    return {
        "id": profile.id,
        "userId": profile.user_id,
        "displayName": profile.display_name,
        "headline": profile.headline,
        "companyName": profile.company_name,
        "jobTitle": profile.job_title,
        "department": profile.department,
        "city": profile.city,
        "country": profile.country,
        "timezone": profile.timezone,
        "preferredLanguage": profile.preferred_language,
        "workEmail": profile.work_email,
        "linkedinProfileUrl": profile.linkedin_profile_url,
        "skills": profile.skills_json or [],
        "education": profile.education_json or [],
        "certifications": profile.certifications_json or [],
        "profileSource": profile.profile_source_json or {},
        "createdAt": profile.created_at,
        "updatedAt": profile.updated_at,
    }


def get_or_create_profile(db: Session, user: User) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if profile is not None:
        return profile

    profile = UserProfile(
        id=generate_id("profile"),
        user_id=user.id,
        display_name=user.name,
        work_email=user.email,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_profile_summary(db: Session, user: User) -> dict:
    return _serialize_profile(get_or_create_profile(db, user))


def update_profile(db: Session, user: User, payload: dict) -> dict:
    profile = get_or_create_profile(db, user)

    field_map = {
        "displayName": "display_name",
        "headline": "headline",
        "companyName": "company_name",
        "jobTitle": "job_title",
        "department": "department",
        "city": "city",
        "country": "country",
        "timezone": "timezone",
        "preferredLanguage": "preferred_language",
        "workEmail": "work_email",
        "linkedinProfileUrl": "linkedin_profile_url",
        "skills": "skills_json",
        "education": "education_json",
        "certifications": "certifications_json",
        "profileSource": "profile_source_json",
    }
    for incoming_key, model_key in field_map.items():
        if incoming_key in payload:
            setattr(profile, model_key, payload[incoming_key])

    if "displayName" in payload and payload["displayName"]:
        user.name = payload["displayName"]

    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)
