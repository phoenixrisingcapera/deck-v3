from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import BillingInvoice, BillingPlan, User, Workspace, WorkspaceSubscription


def _resolve_workspace(db: Session, user: User) -> Workspace | None:
    return db.query(Workspace).filter(Workspace.user_id == user.id).order_by(Workspace.created_at.asc()).first()


def _serialize_plan(plan: BillingPlan) -> dict:
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "monthlyPriceCents": plan.monthly_price_cents,
        "annualPriceCents": plan.annual_price_cents,
        "ctaLabel": plan.cta_label,
        "isHighlighted": plan.is_highlighted,
        "isEnterprise": plan.is_enterprise,
        "seatLabel": plan.seat_label,
        "featureBullets": plan.feature_bullets_json or [],
        "createdAt": plan.created_at,
        "updatedAt": plan.updated_at,
    }


def _serialize_subscription(subscription: WorkspaceSubscription) -> dict:
    return {
        "id": subscription.id,
        "workspaceId": subscription.workspace_id,
        "billingPlanId": subscription.billing_plan_id,
        "status": subscription.status,
        "interval": subscription.interval,
        "seatCount": subscription.seat_count,
        "currentPeriodStart": subscription.current_period_start,
        "currentPeriodEnd": subscription.current_period_end,
        "plan": _serialize_plan(subscription.billing_plan) if subscription.billing_plan is not None else None,
        "createdAt": subscription.created_at,
        "updatedAt": subscription.updated_at,
    }


def _serialize_invoice(invoice: BillingInvoice) -> dict:
    return {
        "id": invoice.id,
        "workspaceSubscriptionId": invoice.workspace_subscription_id,
        "invoiceNumber": invoice.invoice_number,
        "status": invoice.status,
        "amountCents": invoice.amount_cents,
        "currency": invoice.currency,
        "issuedAt": invoice.issued_at,
        "paidAt": invoice.paid_at,
        "createdAt": invoice.created_at,
        "updatedAt": invoice.updated_at,
    }


def list_billing_plans(db: Session) -> list[dict]:
    plans = db.query(BillingPlan).order_by(BillingPlan.monthly_price_cents.asc().nullsfirst(), BillingPlan.name.asc()).all()
    return [_serialize_plan(plan) for plan in plans]


def get_workspace_subscription(db: Session, user: User) -> dict | None:
    workspace = _resolve_workspace(db, user)
    if workspace is None:
        return None

    subscription = (
        db.query(WorkspaceSubscription)
        .options(selectinload(WorkspaceSubscription.billing_plan))
        .filter(WorkspaceSubscription.workspace_id == workspace.id)
        .order_by(WorkspaceSubscription.created_at.desc())
        .first()
    )
    if subscription is None:
        return None
    return _serialize_subscription(subscription)


def switch_workspace_subscription(db: Session, user: User, payload: dict) -> dict | None:
    workspace = _resolve_workspace(db, user)
    if workspace is None:
        return None

    plan_id = payload.get("billingPlanId") or payload.get("planId")
    plan_code = payload.get("planCode")
    plan_query = db.query(BillingPlan)
    if plan_id:
        plan = plan_query.filter(BillingPlan.id == plan_id).one_or_none()
    elif plan_code:
        plan = plan_query.filter(BillingPlan.code == plan_code).one_or_none()
    else:
        plan = None
    if plan is None:
        raise ValueError("Billing plan not found")

    interval = payload.get("interval") or "monthly"
    seat_count = max(int(payload.get("seatCount") or 1), 1)
    now = datetime.utcnow()
    current_period_end = now + (timedelta(days=365) if interval == "annual" else timedelta(days=30))
    subscription = (
        db.query(WorkspaceSubscription)
        .options(selectinload(WorkspaceSubscription.billing_plan))
        .filter(WorkspaceSubscription.workspace_id == workspace.id)
        .order_by(WorkspaceSubscription.created_at.desc())
        .first()
    )
    if subscription is None:
        subscription = WorkspaceSubscription(
            id=generate_id("sub"),
            workspace_id=workspace.id,
            created_at=now,
        )
        db.add(subscription)

    subscription.billing_plan_id = plan.id
    subscription.status = "active"
    subscription.interval = interval
    subscription.seat_count = seat_count
    subscription.current_period_start = now
    subscription.current_period_end = current_period_end
    subscription.updated_at = now

    db.commit()
    db.refresh(subscription)
    subscription.billing_plan = plan
    return _serialize_subscription(subscription)


def list_billing_invoices(db: Session, user: User) -> list[dict]:
    workspace = _resolve_workspace(db, user)
    if workspace is None:
        return []

    invoices = (
        db.query(BillingInvoice)
        .join(WorkspaceSubscription, WorkspaceSubscription.id == BillingInvoice.workspace_subscription_id)
        .filter(WorkspaceSubscription.workspace_id == workspace.id)
        .order_by(BillingInvoice.issued_at.desc().nullslast(), BillingInvoice.created_at.desc())
        .all()
    )
    return [_serialize_invoice(invoice) for invoice in invoices]
