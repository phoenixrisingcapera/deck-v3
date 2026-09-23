from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["super_admin", "admin", "user", "general"]


class PermissionSummary(BaseModel):
    resource: str
    action: str
    granted: bool = True


class UserCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=2)
    role: UserRole = "general"
    company_name: str | None = Field(default=None, alias="companyName", max_length=160)
    accepted_terms: bool = Field(default=False, alias="acceptedTerms")


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: UserRole


class BootstrapUserRoleUpdate(UserRoleUpdate):
    email: EmailStr


class UserSignIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserSummary(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    permissions: list[PermissionSummary] = []


class SessionUser(BaseModel):
    userId: str
    role: UserRole
    email: EmailStr


class WorkspaceSummary(BaseModel):
    id: str
    name: str


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    session: SessionUser
    user: UserSummary
    workspace: WorkspaceSummary


class UserResetPassword(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)
