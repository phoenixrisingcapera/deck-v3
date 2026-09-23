from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class WorkspaceSubscriptionUpdateRequest(BaseModel):
    billingPlanId: str | None = None
    planId: str | None = None
    planCode: str | None = None
    interval: Literal["monthly", "annual"] = "monthly"
    seatCount: int = 1


class BillingPlanSummary(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    monthlyPriceCents: int | None = None
    annualPriceCents: int | None = None
    ctaLabel: str | None = None
    isHighlighted: bool = False
    isEnterprise: bool = False
    seatLabel: str | None = None
    featureBullets: list[str] = []
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class WorkspaceSubscriptionSummary(BaseModel):
    id: str
    workspaceId: str
    billingPlanId: str
    status: str
    interval: str
    seatCount: int
    currentPeriodStart: datetime | None = None
    currentPeriodEnd: datetime | None = None
    plan: BillingPlanSummary | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class BillingInvoiceSummary(BaseModel):
    id: str
    workspaceSubscriptionId: str
    invoiceNumber: str
    status: str
    amountCents: int
    currency: str
    issuedAt: datetime | None = None
    paidAt: datetime | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class BillingPlanListRouteResponse(BaseModel):
    plans: list[BillingPlanSummary]


class WorkspaceSubscriptionRouteResponse(BaseModel):
    subscription: WorkspaceSubscriptionSummary | None = None


class BillingInvoiceListRouteResponse(BaseModel):
    invoices: list[BillingInvoiceSummary]
