"""Shared API guardrails for the DeckAiStack MVP.

Purpose:
- open the correct database session for each request
- resolve the signed-in user from the bearer token
- enforce simple role checks for admin-only routes
- stop users from touching decks or workspaces they do not own

In the MVP this file is the backend gatekeeper, not a product feature module.
It should stay boring and predictable: authenticate first, then check resource
ownership, then let route files call services.

Critical rule:
- a route can compile and still be unsafe if it skips these dependencies
- this file is what turns many route handlers into real user-scoped endpoints
"""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models import Deck, User, Workspace
from app.db.session import AiSessionLocal, SessionLocal
from app.services.platform.auth.auth_session_service import is_auth_session_active
from app.services.admin.security_audit import record_security_event

bearer_scheme = HTTPBearer(auto_error=False)


async def require_bearer_credentials(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> HTTPAuthorizationCredentials:
    """Reject a missing bearer token before opening a database dependency."""

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return credentials


def _authenticate_session_user(db: Session, payload: dict[str, str]) -> User | None:
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None:
        return None
    if not is_auth_session_active(db, user_id=user.id, token_jti=payload["jti"]):
        return None
    return user


def get_db() -> Generator[Session, None, None]:
    # Main product database session.
    # Use this for deck, workspace, artifact, and workflow state reads/writes.
    try:
        db = SessionLocal()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is not available") from exc
    try:
        yield db
    finally:
        db.close()


def get_ai_db() -> Generator[Session, None, None]:
    # AI database session for vector chunks, telemetry, and AI-support data.
    # Falls back to core DB if AI_DATABASE_URL is not configured.
    try:
        db = AiSessionLocal()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI database is not available") from exc
    try:
        yield db
    finally:
        db.close()


def get_user_db() -> Generator[Session, None, None]:
    # Core database is the primary auth/session source of truth.
    try:
        db = SessionLocal()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Core database is not available") from exc
    try:
        yield db
    finally:
        db.close()


def get_billing_db() -> Generator[Session, None, None]:
    # Core database is the primary billing source of truth.
    try:
        db = SessionLocal()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Core database is not available") from exc
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(require_bearer_credentials),
    # DISABLED: A separate get_user_db dependency held one pool connection for
    # authentication while protected routes requested a second connection.
    # With parallel Smart Deck loads this exhausted the production pool and
    # deadlocked requests until the pool timeout.
    # db: Session = Depends(get_user_db),
    # NEW: Reuse FastAPI's request-cached core session for auth and route data.
    db: Session = Depends(get_db),
) -> User:
    # MVP auth contract:
    # every protected frontend call should arrive here with a bearer token that
    # originated from the sign-in flow.
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        # Decode + validate the JWT before touching the database.
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user = _authenticate_session_user(db, payload)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    request.state.auth_payload = payload
    return user


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    # DISABLED: See get_current_user; a second request-scoped core session can
    # exhaust a small connection pool under concurrent authenticated requests.
    # db: Session = Depends(get_user_db),
    # NEW: Optional authentication shares the route's request-cached session.
    db: Session = Depends(get_db),
) -> User | None:
    # Optional-auth variant used by endpoints that should accept both signed-in
    # and anonymous callers, such as failure reporting.
    #
    # It follows the same token + session validation path as get_current_user(),
    # but returns None instead of raising 401 when auth is missing or invalid.
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        return None

    user = _authenticate_session_user(db, payload)
    if user is None:
        return None
    request.state.auth_payload = payload
    return user


def require_roles(*allowed_roles: str):
    # Small admin/operator guard.
    # Use this only when a route is truly role-based, not merely resource-based.
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user

    return dependency


def user_can_access_workspace(user: User, workspace: Workspace) -> bool:
    # MVP rule:
    # normal users only see their own workspace; super_admin can cross workspace
    # boundaries for support and diagnostics.
    return user.role == "super_admin" or workspace.user_id == user.id


def user_can_access_deck(user: User, deck: Deck) -> bool:
    # Deck ownership is slightly wider than `deck.user_id == user.id` because
    # some deck records are effectively owned through the workspace relation.
    if user.role == "super_admin":
        return True
    if deck.user_id == user.id:
        return True
    return bool(deck.workspace and deck.workspace.user_id == user.id)


def get_user_workspace_or_404(db: Session, user: User, workspace_id: str) -> Workspace:
    # Return 404, not 403, so callers cannot probe whether another workspace ID
    # exists.
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).one_or_none()
    if workspace is None or not user_can_access_workspace(user, workspace):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


def get_user_deck_or_404(db: Session, user: User, deck_id: str) -> Deck:
    # Same pattern as workspace access: hide existence for unauthorized users.
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None or not user_can_access_deck(user, deck):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return deck


def _audit_super_admin_deck_access(db: Session, request: Request, user: User, deck: Deck) -> None:
    # Only log elevated cross-user reads.
    # Normal owners reading their own deck are not special enough to audit here.
    if user.role != "super_admin":
        return

    workspace_owner_id = deck.workspace.user_id if deck.workspace else None
    if deck.user_id == user.id or workspace_owner_id == user.id:
        return

    record_security_event(
        db,
        action="resource.access.super_admin",
        result="success",
        actor=user,
        resource_type="deck",
        resource_id=deck.id,
        request=request,
        details={"deckUserId": deck.user_id, "workspaceUserId": workspace_owner_id},
        commit=True,
    )


def _audit_super_admin_workspace_access(db: Session, request: Request, user: User, workspace: Workspace) -> None:
    # Same idea as deck audit logging, but for cross-user workspace access.
    if user.role != "super_admin" or workspace.user_id == user.id:
        return

    record_security_event(
        db,
        action="resource.access.super_admin",
        result="success",
        actor=user,
        resource_type="workspace",
        resource_id=workspace.id,
        request=request,
        details={"workspaceUserId": workspace.user_id},
        commit=True,
    )


def require_resource_access(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    # This is the broad MVP route guard used in app/main.py.
    #
    # It does not know product business logic. It only knows:
    # - if a route includes `deck_id`, verify the user may touch that deck
    # - if a route includes `workspace_id`, verify the user may touch that workspace
    #
    # This is why route parameter naming matters. The current backend mostly
    # standardizes on `deck_id` and `workspace_id`; routes using different names
    # will bypass this automatic ownership check unless they validate manually.
    deck_id = request.path_params.get("deck_id")
    if isinstance(deck_id, str) and deck_id:
        try:
            deck = get_user_deck_or_404(db, user, deck_id)
            _audit_super_admin_deck_access(db, request, user, deck)
        except HTTPException:
            # Record denied access attempts before re-raising the same 404/403
            # decision so operators can audit abuse or routing mistakes.
            record_security_event(
                db,
                action="resource.access",
                result="denied",
                actor=user,
                resource_type="deck",
                resource_id=deck_id,
                request=request,
                commit=True,
            )
            raise

    workspace_id = request.path_params.get("workspace_id") or request.query_params.get("workspace_id")
    if isinstance(workspace_id, str) and workspace_id:
        try:
            workspace = get_user_workspace_or_404(db, user, workspace_id)
            _audit_super_admin_workspace_access(db, request, user, workspace)
        except HTTPException:
            record_security_event(
                db,
                action="resource.access",
                result="denied",
                actor=user,
                resource_type="workspace",
                resource_id=workspace_id,
                request=request,
                commit=True,
            )
            raise

    # Return the resolved user so route handlers can depend on this guard and
    # still receive the authenticated actor object.
    return user
