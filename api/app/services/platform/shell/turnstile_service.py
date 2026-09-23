from __future__ import annotations

import json
from urllib import error as url_error
from urllib import parse, request

from fastapi import HTTPException, status

from app.core.config import settings

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(token: str | None, *, remote_ip: str | None = None) -> None:
    if not settings.turnstile_secret_key:
        return
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification is required.",
        )

    form = {
        "secret": settings.turnstile_secret_key,
        "response": token.strip(),
    }
    if remote_ip:
        form["remoteip"] = remote_ip

    payload = parse.urlencode(form).encode("utf-8")
    verify_request = request.Request(
        TURNSTILE_VERIFY_URL,
        data=payload,
        headers={"content-type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(verify_request, timeout=settings.turnstile_verify_timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, url_error.URLError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CAPTCHA verification is temporarily unavailable.",
        ) from exc

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAPTCHA verification failed.",
        )
