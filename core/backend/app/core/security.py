"""
Security utilities for authentication and authorization.

CRITICAL PATH: Password hashing → JWT creation → JWT validation → User authentication

This file provides:
1. Password hashing (PBKDF2 with 200k iterations)
2. JWT token creation with proper claims
3. JWT token validation with security checks
4. Secure ID generation

USER JOURNEY:
1. User registers → password hashed with PBKDF2 (200k iterations)
2. User logs in → password verified against hash
3. Server creates JWT with: user_id, expiry, issuer, audience, jti
4. Client sends JWT with requests
5. Server validates JWT: signature, expiry, issuer, audience, jti
6. Server checks session is still active (not revoked)

SECURITY FEATURES:
- PBKDF2: Industry-standard password hashing (200k iterations)
- HMAC comparison: Prevents timing attacks on password verification
- JWT claims: iss (issuer), aud (audience), iat (issued at), exp (expiry), jti (unique ID)
- Token expiry: Configurable, default 60 minutes
- Session tracking: Each token has unique jti, can be revoked

TOKEN STRUCTURE:
{
  "sub": "user_abc123",           # User ID
  "iss": "deck-aistack-codes",    # Issuer
  "aud": "deck-aistack-codes",    # Audience
  "iat": 1234567890,              # Issued at (timestamp)
  "exp": 1234571490,              # Expiry (timestamp)
  "jti": "unique_token_id"        # Unique token ID (for revocation)
}
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


JWT_ALGORITHM = "HS256"


def generate_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def hash_password(password: str, salt: str | None = None) -> str:
    password_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), password_salt.encode("utf-8"), 200_000)
    return f"{password_salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored_digest = password_hash.split("$", 1)
    except ValueError:
        return False

    candidate = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, stored_digest)


def create_access_token(payload: dict[str, str], expires_minutes: int | None = None) -> str:
    data = build_access_token_payload(payload, expires_minutes=expires_minutes)
    return jwt.encode(
        data,
        settings.auth_secret_key,
        algorithm=JWT_ALGORITHM,
        headers={"typ": "JWT", "kid": settings.auth_secret_key_id},
    )


def build_access_token_payload(payload: dict[str, str], expires_minutes: int | None = None) -> dict[str, Any]:
    issued_at = datetime.now(UTC)
    expiry = issued_at + timedelta(minutes=expires_minutes or settings.auth_token_expiry_minutes)
    return {
        **payload,
        "iss": settings.auth_token_issuer,
        "aud": settings.auth_token_audience,
        "iat": int(issued_at.timestamp()),
        "exp": int(expiry.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
        if header.get("kid") != settings.auth_secret_key_id:
            raise ValueError("Invalid token key id")
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[JWT_ALGORITHM],
            issuer=settings.auth_token_issuer,
            audience=settings.auth_token_audience,
            leeway=60,
            options={
                "require": ["iss", "aud", "sub", "iat", "exp", "jti"],
            },
        )
    except InvalidTokenError as exc:
        raise ValueError(str(exc)) from exc

    if not payload.get("sub"):
        raise ValueError("Invalid token subject")
    if not payload.get("jti"):
        raise ValueError("Invalid token id")
    try:
        issued_at = int(payload["iat"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid token issued-at") from exc
    try:
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid token expiry") from exc
    now = int(datetime.now(UTC).timestamp())
    if issued_at > now + 60:
        raise ValueError("Token issued in the future")
    if expires_at < now:
        raise ValueError("Token expired")
    return payload
