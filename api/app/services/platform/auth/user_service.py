from __future__ import annotations

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

import jwt
from pydantic import EmailStr

from app.core.config import settings
from app.core.security import JWT_ALGORITHM, build_access_token_payload, generate_id, hash_password, verify_password
from app.db.models import Permission, User, UserProfile, Workspace
from app.schemas.user import PermissionSummary, UserCreate
from app.services.platform.auth.auth_session_service import create_auth_session

DEFAULT_ROLE_PERMISSIONS: dict[str, list[tuple[str, str]]] = {
    "super_admin": [
        ("users", "create"),
        ("users", "assign_roles"),
        ("decks", "manage_all"),
        ("admin_pages", "view"),
    ],
    "admin": [
        ("site_pages", "edit"),
        ("marketing_pages", "publish"),
    ],
    "user": [
        ("decks", "create"),
        ("smart_deck", "use"),
        ("smart_edit", "use"),
        ("design_batches", "view"),
        ("deck", "export"),
    ],
    "general": [
        ("interest_form", "submit"),
    ],
}


def serialize_permission(permission: Permission) -> dict:
    return PermissionSummary(
        resource=permission.resource,
        action=permission.action,
        granted=permission.granted,
    ).model_dump()


def serialize_user(user: User) -> dict:
    permissions = sorted(user.permissions, key=lambda item: (item.resource, item.action))
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "permissions": [serialize_permission(permission) for permission in permissions],
    }


def serialize_workspace(workspace: Workspace) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
    }


def ensure_role_permissions(db: Session, user: User, role: str) -> None:
    expected = set(DEFAULT_ROLE_PERMISSIONS.get(role, []))
    existing = {(item.resource, item.action) for item in user.permissions}

    for resource, action in expected - existing:
        db.add(Permission(user_id=user.id, resource=resource, action=action, granted=True))


def update_user_role(db: Session, user: User, role: str) -> User:
    user.role = role
    ensure_role_permissions(db, user, role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def ensure_workspace(db: Session, user: User, *, workspace_name: str | None = None) -> Workspace:
    workspace = (
        db.query(Workspace)
        .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
        .filter(Workspace.user_id == user.id)
        .first()
    )
    clean_workspace_name = _clean_optional_text(workspace_name)
    if workspace is not None:
        if clean_workspace_name and workspace.name != clean_workspace_name:
            workspace.name = clean_workspace_name
        return workspace

    workspace = Workspace(
        id=generate_id("ws"),
        name=clean_workspace_name or f"{user.name.split()[0]}'s Workspace",
        user_id=user.id,
    )
    db.add(workspace)
    return workspace


def ensure_signup_profile(db: Session, user: User, payload: UserCreate) -> None:
    company_name = _clean_optional_text(payload.company_name)
    if not company_name and not payload.accepted_terms:
        return

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if profile is None:
        profile = UserProfile(
            id=generate_id("profile"),
            user_id=user.id,
            display_name=user.name,
            work_email=user.email,
        )
        db.add(profile)

    if company_name:
        profile.company_name = company_name

    if payload.accepted_terms:
        source = dict(profile.profile_source_json or {})
        source["signup"] = {
            **(source.get("signup") if isinstance(source.get("signup"), dict) else {}),
            "acceptedTerms": True,
            "acceptedAt": datetime.utcnow().isoformat() + "Z",
        }
        profile.profile_source_json = source


def create_user(db: Session, payload: UserCreate) -> User:
    normalized_email = payload.email.strip().lower()
    existing = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing is not None:
        raise ValueError("User already exists")

    user = User(
        id=generate_id("usr"),
        email=normalized_email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    ensure_role_permissions(db, user, payload.role)
    ensure_workspace(db, user, workspace_name=payload.company_name)
    ensure_signup_profile(db, user, payload)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def build_auth_response(db: Session, user: User) -> dict:
    workspace = ensure_workspace(db, user)
    db.flush()
    token_payload = build_access_token_payload(
        {
            "sub": user.id,
            "role": user.role,
            "email": user.email,
        }
    )
    access_token = jwt.encode(
        token_payload,
        settings.auth_secret_key,
        algorithm=JWT_ALGORITHM,
        headers={"typ": "JWT", "kid": settings.auth_secret_key_id},
    )
    create_auth_session(db, user_id=user.id, token_payload=token_payload)
    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "session": {
            "userId": user.id,
            "role": user.role,
            "email": user.email,
        },
        "user": serialize_user(user),
        "workspace": serialize_workspace(workspace),
    }


def list_users(db: Session) -> list[dict]:
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [serialize_user(user) for user in users]
