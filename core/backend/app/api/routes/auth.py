"""
Authentication routes for user registration and login.

CRITICAL PATH: User sign-in → JWT token → Session cookie → Authenticated requests

This file handles:
1. User registration (/auth/sign-up)
2. User login (/auth/sign-in)
3. Session validation
4. Rate limiting to prevent abuse
5. Security audit logging

USER JOURNEY:
1. User submits email/password to /auth/sign-in
2. Server validates credentials against database
3. Server creates JWT token with user ID, expiry, claims
4. Server returns token to client
5. Client stores token (cookie/localStorage)
6. Client sends token with every request
7. Server validates token on each request (see deps.py:get_current_user)

SECURITY FEATURES:
- Rate limiting: 30 attempts per 15 minutes per IP
- Password hashing: PBKDF2 with 200k iterations
- JWT validation: Signature, expiry, issuer, audience checks
- Session tracking: Active session validation
- Audit logging: All auth events logged for security review
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_db
from app.core.config import settings
from app.db.models import User
from app.schemas.user import AuthSessionResponse, UserCreate, UserResetPassword, UserSignIn, UserSummary
from app.services.platform.auth.auth_session_service import revoke_auth_session
from app.services.platform.auth.user_service import (
    authenticate_user,
    build_auth_response,
    create_user,
    serialize_user,
)
from app.services.platform.billing.rate_limit_service import enforce_rate_limit, enforce_rate_limits
from app.services.admin.security_audit import record_security_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _sign_up_user(payload: UserCreate, request: Request, db: Session) -> dict:
    enforce_rate_limit(f"auth:signup:ip:{_client_ip(request)}", db=db, limit=10, window_seconds=3600)
    enforce_rate_limit(f"auth:signup:email:{payload.email.lower()}", db=db, limit=3, window_seconds=3600)
    if not payload.accepted_terms:
        record_security_event(
            db,
            action="auth.sign_up",
            result="denied",
            actor_email=payload.email,
            resource_type="user",
            request=request,
            details={"reason": "terms_not_accepted"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You must accept the terms to create an account")

    if not settings.public_signup_enabled:
        record_security_event(
            db,
            action="auth.sign_up",
            result="denied",
            actor_email=payload.email,
            resource_type="user",
            request=request,
            details={"reason": "public_signup_disabled"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public sign-up is disabled")

    # Public self-signups must land in the real product surface with product
    # permissions, not the interest-form-only general role.
    public_payload = payload.model_copy(update={"role": "user"})
    try:
        user = create_user(db, public_payload)
    except ValueError as exc:
        record_security_event(
            db,
            action="auth.sign_up",
            result="failure",
            actor_email=payload.email,
            resource_type="user",
            request=request,
            details={"reason": str(exc)},
            commit=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_security_event(
        db,
        action="auth.sign_up",
        result="success",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        request=request,
        commit=True,
    )
    return build_auth_response(db, user)


@router.post("/sign-up", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def sign_up(payload: UserCreate, request: Request, db: Session = Depends(get_user_db)) -> dict:
    return _sign_up_user(payload, request, db)


@router.post("/signup", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def sign_up_compat(payload: UserCreate, request: Request, db: Session = Depends(get_user_db)) -> dict:
    """Compatibility alias for older frontend/auth integrations."""
    return _sign_up_user(payload, request, db)


def _sign_in_user(payload: UserSignIn, request: Request, db: Session) -> dict:
    enforce_rate_limits(
        [
            (f"auth:signin:ip:{_client_ip(request)}", 30, 900),
            (f"auth:signin:email:{payload.email.lower()}", 10, 900),
        ],
        db=db,
    )
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        record_security_event(
            db,
            action="auth.sign_in",
            result="failure",
            actor_email=payload.email,
            resource_type="user",
            request=request,
            details={"reason": "invalid_credentials"},
            commit=False,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    record_security_event(
        db,
        action="auth.sign_in",
        result="success",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        request=request,
        commit=False,
    )
    return build_auth_response(db, user)


@router.post("/sign-in", response_model=AuthSessionResponse)
def sign_in(payload: UserSignIn, request: Request, db: Session = Depends(get_user_db)) -> dict:
    return _sign_in_user(payload, request, db)


@router.post("/signin", response_model=AuthSessionResponse)
def sign_in_compat(payload: UserSignIn, request: Request, db: Session = Depends(get_user_db)) -> dict:
    """Compatibility alias for older frontend/auth integrations."""
    return _sign_in_user(payload, request, db)


@router.post("/login", response_model=AuthSessionResponse)
def login_compat(payload: UserSignIn, request: Request, db: Session = Depends(get_user_db)) -> dict:
    """Compatibility alias for older frontend/auth integrations."""
    return _sign_in_user(payload, request, db)


@router.get("/me", response_model=UserSummary)
def me(current_user: User = Depends(get_current_user)) -> dict:
    return serialize_user(current_user)


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token_payload = getattr(request.state, "auth_payload", {})
    token_jti = token_payload.get("jti")
    if token_jti:
        revoke_auth_session(db, user_id=current_user.id, token_jti=token_jti)
    record_security_event(
        db,
        action="auth.logout",
        result="success",
        actor=current_user,
        resource_type="auth_session",
        resource_id=token_jti,
        request=request,
        commit=True,
    )
    return {"status": "ok"}


@router.post("/reset-password")
def reset_password(
    payload: UserResetPassword,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db),
) -> dict[str, str]:
    """Change the authenticated user's password directly in-platform."""
    from app.core.security import hash_password, verify_password

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    enforce_rate_limit(f"auth:reset-password:ip:{_client_ip(request)}", db=db, limit=5, window_seconds=3600)
    enforce_rate_limit(f"auth:reset-password:email:{current_user.email.lower()}", db=db, limit=3, window_seconds=3600)

    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)

    record_security_event(
        db,
        action="auth.reset_password",
        result="success",
        actor=current_user,
        resource_type="user",
        resource_id=current_user.id,
        request=request,
        commit=True,
    )

    return {"status": "ok"}
