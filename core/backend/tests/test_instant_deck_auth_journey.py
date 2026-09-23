from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.api.routes.auth import logout, sign_in, sign_up
from app.core.config import settings
from app.db.base import CoreBase
from app.schemas.user import UserCreate, UserSignIn


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_email_password_session_lifecycle(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(settings, "public_signup_enabled", True)
    try:
        signup = sign_up(
            UserCreate(
                email="owner@example.com",
                password="correct-horse-1",
                name="Ordinary Owner",
                companyName="Owner Workspace",
                acceptedTerms=True,
            ),
            _request(),
            db,
        )
        assert signup["user"]["role"] == "user"
        assert signup["workspace"]["name"] == "Owner Workspace"

        signup_request = _request()
        signup_user = get_current_user(signup_request, _credentials(signup["access_token"]), db)
        assert signup_user.email == "owner@example.com"

        signin = sign_in(UserSignIn(email="owner@example.com", password="correct-horse-1"), _request(), db)
        signin_request = _request()
        signin_user = get_current_user(signin_request, _credentials(signin["access_token"]), db)
        assert signin_user.id == signup_user.id

        assert logout(signin_request, signin_user, db) == {"status": "ok"}
        try:
            get_current_user(_request(), _credentials(signin["access_token"]), db)
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("A logged-out session remained valid")

        assert get_current_user(_request(), _credentials(signup["access_token"]), db).id == signup_user.id
    finally:
        db.close()
        engine.dispose()


def test_public_signup_requires_explicit_enablement(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(settings, "public_signup_enabled", False)
    try:
        try:
            sign_up(
                UserCreate(
                    email="disabled@example.com",
                    password="correct-horse-2",
                    name="Disabled Owner",
                    acceptedTerms=True,
                ),
                _request(),
                db,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail == "Public sign-up is disabled"
        else:
            raise AssertionError("Public signup succeeded while disabled")
    finally:
        db.close()
        engine.dispose()
