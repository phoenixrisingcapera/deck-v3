from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DeploymentReadinessCheck(BaseModel):
    status: str
    ok: bool
    message: str
    details: dict[str, Any] | None = None


class DeploymentReadinessResponse(BaseModel):
    ok: bool
    status: str
    environment: str
    serviceRole: str
    checkedAt: str
    checks: dict[str, DeploymentReadinessCheck]
    summary: dict[str, Any]
