"""Durable accounting/checkpoint primitives for one Instant HTML operation."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from typing import Any, Callable
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.openai_full_html_policy import (
    FULL_HTML_MAX_INPUT_TOKENS,
    FULL_HTML_MAX_OUTPUT_TOKENS,
    FULL_HTML_MAX_SOURCE_SLIDES,
    FULL_HTML_OPENAI_MODEL,
    estimate_openai_cost_cents,
    require_full_html_openai_model,
)
from app.core.security import generate_id
from app.core.config import settings
from app.core.workspace_ai_crypto import get_workspace_ai_fernet
from app.core.instant_html_raw_checkpoint_crypto import (
    RAW_CHECKPOINT_ENCRYPTION_PURPOSE,
    get_instant_html_raw_checkpoint_fernet,
)
from app.db.models import GenerationJob, InstantDeckArtifactCleanupTask, InstantDeckCompilation, InstantDeckHtmlArtifact, InstantDeckOperation, InstantDeckProviderAttempt, InstantDeckRenderCapability, SecurityAuditEvent, User, WorkflowJob
from app.services.platform.billing.ai_usage_quota_service import (
    ai_operation_budget_status,
    cancel_ai_operation_budget,
    reconcile_ai_operation_budget,
    reserve_ai_operation_budget,
)
from app.services.storage.artifact_storage import get_upload_storage, promote_upload
from app.core.instant_deck_request_policy import MAX_PROVIDER_REQUEST_STARTS
INSTANT_HTML_UNAVAILABLE_REASON = "instant_html_unavailable"
INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE = "Instant HTML generation is unavailable for this request."
INSTANT_CONTEXT_PREPARATION_FAILURE_REASONS = {
    "instant_request_context_persistence_failed",
    "instant_request_context_feasibility_failed",
    "instant_context_ownership_failed",
    "instant_baseline_validation_failed",
    "instant_typed_context_build_failed",
}
INSTANT_CONTEXT_PREPARATION_SAFE_MESSAGE = (
    "We couldn't prepare the redesigned deck for generation. Your uploaded source is saved. "
    "Start a new redesign, or contact support if the problem repeats."
)
MANUAL_RECONCILIATION_MAX_AGE = timedelta(hours=24)
CLEANUP_TASK_STALE_AFTER = timedelta(minutes=15)
REQUEST_CONTEXT_TERMINAL_RETENTION = timedelta(days=7)
RECOVERY_CREDIT_WAIVER_STATUS = "recovery_waived"
RECOVERY_CREDIT_WAIVER_REASON = "provider_checkpoint_recompile_no_second_product_credit"


def _is_preview_render_runtime() -> bool:
    normalize = lambda value: str(value or "").strip().lower().replace("-", "_")
    job_types = {
        normalize(item)
        for item in str(os.getenv("DECK_WORKER_JOB_TYPES") or "").split(",")
        if item.strip()
    }
    kind = normalize(os.getenv("WORKER_KIND"))
    role = normalize(os.getenv("APP_ROLE") or settings.app_role)
    return role == "worker_preview_render" or kind == "preview_render" or "preview_render" in job_types


def register_artifact_cleanup_tasks(
    db: Session, *, deck_id: str | None, operation_id: str | None,
    attempt_id: str | None, storage_keys: list[str]
) -> list[InstantDeckArtifactCleanupTask]:
    if not storage_keys or len(storage_keys) != len(set(storage_keys)):
        raise ValueError("Cleanup staging requires unique prospective storage keys.")
    tasks: list[InstantDeckArtifactCleanupTask] = []
    for storage_key in storage_keys:
        task = db.query(InstantDeckArtifactCleanupTask).filter(
            InstantDeckArtifactCleanupTask.storage_key == storage_key
        ).one_or_none()
        if task is None:
            task = InstantDeckArtifactCleanupTask(
                id=generate_id("htmlcleanup"), storage_key=storage_key, deck_id=deck_id,
                operation_id=operation_id, provider_attempt_id=attempt_id,
                status="promotion_pending", locked_by=f"promotion:{attempt_id}",
                locked_at=datetime.utcnow(),
            )
            db.add(task)
        elif task.status == "completed":
            task.status = "promotion_pending"
            task.completed_at = None
            task.locked_by = f"promotion:{attempt_id}"
            task.locked_at = datetime.utcnow()
        tasks.append(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        tasks = db.query(InstantDeckArtifactCleanupTask).filter(
            InstantDeckArtifactCleanupTask.storage_key.in_(storage_keys)
        ).all()
        if len(tasks) != len(storage_keys):
            raise
    if any(
        task.storage_key not in storage_keys
        or task.status not in {"promotion_pending", "completed", "canceled"}
        or task.deck_id != deck_id
        or task.operation_id != operation_id
        or task.provider_attempt_id != attempt_id
        for task in tasks
    ):
        raise RuntimeError("Prospective storage cleanup ownership is invalid.")
    return tasks


def complete_artifact_cleanup_tasks(db: Session, storage_keys: list[str]) -> None:
    now = datetime.utcnow()
    for task in db.query(InstantDeckArtifactCleanupTask).filter(
        InstantDeckArtifactCleanupTask.storage_key.in_(storage_keys)
    ).with_for_update().all():
        task.status = "canceled"
        task.completed_at = now
        task.locked_by = None
        task.locked_at = None


def require_staged_cleanup_tasks(db: Session, storage_keys: list[str]) -> None:
    tasks = db.query(InstantDeckArtifactCleanupTask).filter(
        InstantDeckArtifactCleanupTask.storage_key.in_(storage_keys)
    ).with_for_update().all()
    if len(tasks) != len(storage_keys) or any(task.status != "promotion_pending" for task in tasks):
        raise RuntimeError("Every prospective object requires one durable pending cleanup row.")


def require_canceled_cleanup_tasks(
    db: Session, storage_keys: list[str], *, deck_id: str,
    operation_id: str, attempt_id: str,
) -> None:
    tasks = db.query(InstantDeckArtifactCleanupTask).filter(
        InstantDeckArtifactCleanupTask.storage_key.in_(storage_keys)
    ).all()
    if len(tasks) != len(storage_keys) or any(
        task.status != "canceled"
        or task.deck_id != deck_id
        or task.operation_id != operation_id
        or task.provider_attempt_id != attempt_id
        for task in tasks
    ):
        raise RuntimeError("Published objects require exact canceled cleanup ownership.")


def reconcile_artifact_cleanup_tasks(
    db: Session,
    *,
    worker_id: str,
    limit: int = 25,
    operation_id: str | None = None,
) -> int:
    stale_before = datetime.utcnow() - CLEANUP_TASK_STALE_AFTER
    try:
        query = db.query(InstantDeckArtifactCleanupTask).filter(
            or_(
                InstantDeckArtifactCleanupTask.status.in_(["pending", "retry_pending"]),
                and_(
                    InstantDeckArtifactCleanupTask.status.in_(["promotion_pending", "deleting"]),
                    or_(
                        InstantDeckArtifactCleanupTask.locked_at <= stale_before,
                        and_(
                            InstantDeckArtifactCleanupTask.locked_at.is_(None),
                            InstantDeckArtifactCleanupTask.created_at <= stale_before,
                        ),
                    ),
                ),
            )
        )
        if operation_id is not None:
            query = query.filter(
                InstantDeckArtifactCleanupTask.operation_id == operation_id
            )
        tasks = query.order_by(
            InstantDeckArtifactCleanupTask.created_at.asc(), InstantDeckArtifactCleanupTask.id.asc()
        ).with_for_update(skip_locked=True).limit(limit).all()
    except (OperationalError, ProgrammingError) as exc:
        message = str(getattr(exc, "orig", exc)).lower()
        if "instant_deck_artifact_cleanup_tasks" in message and any(
            marker in message for marker in ("no such table", "does not exist", "undefined table")
        ):
            db.rollback()
            return 0
        raise
    if not tasks:
        return 0
    now = datetime.utcnow()
    for task in tasks:
        task.status = "deleting"
        task.locked_by = worker_id
        task.locked_at = now
        task.attempt_count = int(task.attempt_count or 0) + 1
    db.commit()
    storage = get_upload_storage()
    completed = 0
    for task_id in [task.id for task in tasks]:
        task = db.query(InstantDeckArtifactCleanupTask).filter(
            InstantDeckArtifactCleanupTask.id == task_id,
            InstantDeckArtifactCleanupTask.status == "deleting",
            InstantDeckArtifactCleanupTask.locked_by == worker_id,
        ).with_for_update().one_or_none()
        if task is None:
            continue
        try:
            storage.delete(task.storage_key)
            if storage.object_exists(task.storage_key):
                raise RuntimeError("cleanup object remains")
        except Exception:
            task.status = "retry_pending"
            task.last_error_at = datetime.utcnow()
            result = "failure"
        else:
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            completed += 1
            result = "success"
        task.locked_by = None
        task.locked_at = None
        db.add(SecurityAuditEvent(
            id=generate_id("audit"), actor_user_id=None,
            action="instant_html.artifact_cleanup.retry", resource_type="instant_deck_operation",
            resource_id=task.operation_id, result=result,
            details_json={"cleanupTaskId": task.id, "attempt": task.attempt_count},
        ))
        db.commit()
    return completed


def complete_absent_operation_cleanup_tasks(
    db: Session, *, operation_id: str
) -> int:
    """Release one operation's promotion guard only when every object is absent.

    This supports an immediate retry after a pre-write local/storage failure
    without weakening the normal stale-delete lease. It never deletes data.
    """
    tasks = db.query(InstantDeckArtifactCleanupTask).filter(
        InstantDeckArtifactCleanupTask.operation_id == operation_id,
        InstantDeckArtifactCleanupTask.status == "promotion_pending",
    ).with_for_update().all()
    if not tasks:
        return 0
    storage = get_upload_storage()
    if any(storage.object_exists(task.storage_key) for task in tasks):
        raise RuntimeError("Promotion cleanup objects still exist; stale reconciliation is required.")
    now = datetime.utcnow()
    for task in tasks:
        task.status = "completed"
        task.completed_at = now
        task.locked_by = None
        task.locked_at = None
    db.commit()
    return len(tasks)

MODEL_PRICING_USD_PER_1K: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("openai", "gpt-4.1"): (Decimal("0.002"), Decimal("0.008")),
    ("openai", "gpt-4.1-mini"): (Decimal("0.0004"), Decimal("0.0016")),
    ("openai", "gpt-4o"): (Decimal("0.005"), Decimal("0.015")),
    ("openai", FULL_HTML_OPENAI_MODEL): (Decimal("0.00125"), Decimal("0.010")),
    ("anthropic", "claude-sonnet-4-5"): (Decimal("0.003"), Decimal("0.015")),
    ("anthropic", "claude-opus-4-1"): (Decimal("0.015"), Decimal("0.075")),
    ("openrouter", "openai/gpt-4o"): (Decimal("0.005"), Decimal("0.015")),
    ("openrouter", "openai/gpt-4.1-mini"): (Decimal("0.0004"), Decimal("0.0016")),
    ("dashscope", "qwen3.7-plus"): (Decimal("0.0008"), Decimal("0.002")),
    ("dashscope", "qwen-plus"): (Decimal("0.0008"), Decimal("0.002")),
}


def estimate_model_cost_cents(provider: str, model: str | None, *, input_tokens: int, output_tokens: int) -> float | None:
    if not model:
        return None
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip().lower()
    rates = MODEL_PRICING_USD_PER_1K.get((normalized_provider, normalized_model))
    if rates is None:
        return None
    input_rate, output_rate = rates
    usd = Decimal(max(0, input_tokens)) / Decimal(1000) * input_rate
    usd += Decimal(max(0, output_tokens)) / Decimal(1000) * output_rate
    return float((usd * Decimal(100)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def require_next_request_cost_budget(
    operation: InstantDeckOperation,
    *,
    provider: str,
    model: str | None,
    estimated_input_tokens: int,
    max_output_tokens: int,
) -> float:
    if provider.strip().lower() == "openai":
        require_full_html_openai_model(model)
        estimate = float(estimate_openai_cost_cents(
            input_tokens=estimated_input_tokens,
            output_tokens=max_output_tokens,
        ))
    else:
        estimate = estimate_model_cost_cents(
            provider,
            model,
            input_tokens=estimated_input_tokens,
            output_tokens=max_output_tokens,
        )
    if estimate is None:
        if operation.max_cost_cents is not None:
            raise InstantOperationBudgetExceeded("Configured provider/model pricing is unavailable; request cannot be cost-bounded.")
        # An uncapped operation must not become blocked by a missing internal
        # tariff table. Tokens/provider IDs are still recorded; cost remains
        # explicitly unknown until the provider supplies a reconcilable value.
        return 0.0
    actual = float(getattr(operation, "actual_provider_cost_cents", 0.0) or 0.0)
    reserved = float(getattr(operation, "reserved_provider_cost_cents", 0.0) or 0.0)
    if operation.max_cost_cents is not None and actual + reserved + estimate > operation.max_cost_cents:
        raise InstantOperationBudgetExceeded("The next provider request could exceed the Instant Deck cost budget.")
    return estimate


class InstantOperationConflict(ValueError):
    pass


class ActiveInstantOperationConflict(InstantOperationConflict):
    """A different non-terminal Instant command already owns this deck."""

    pass


class InstantProviderAttestationUnavailable(RuntimeError):
    """Transient process readiness loss; queued customer work remains eligible."""

    code = INSTANT_HTML_UNAVAILABLE_REASON
    retryable = True


class InstantOperationBudgetExceeded(ValueError):
    pass


def _settle_attempt_reservation(
    operation: InstantDeckOperation,
    attempt: InstantDeckProviderAttempt,
) -> bool:
    """Release one attempt's request reservation exactly once under row locks."""

    metadata = dict(getattr(attempt, "outcome_metadata_json", None) or {})
    if metadata.get("reservationSettled") is True:
        return False
    reservation = max(0.0, float(getattr(attempt, "reserved_cost_cents", 0.0) or 0.0))
    operation.reserved_provider_cost_cents = max(
        0.0,
        float(getattr(operation, "reserved_provider_cost_cents", 0.0) or 0.0) - reservation,
    )
    metadata["reservationSettled"] = True
    attempt.outcome_metadata_json = metadata
    return True


def _reconcile_manual_attempt_cost(
    operation: InstantDeckOperation,
    attempt: InstantDeckProviderAttempt,
    *,
    decision: str,
) -> None:
    """Transfer an unknown processed request's estimate to actual cost once."""

    metadata = dict(getattr(attempt, "outcome_metadata_json", None) or {})
    prior_decision = metadata.get("manualReconciliationDecision")
    if prior_decision is not None:
        if prior_decision != decision:
            raise InstantOperationConflict("Provider attempt was already reconciled with another decision.")
        return
    reservation = max(0.0, float(getattr(attempt, "reserved_cost_cents", 0.0) or 0.0))
    if decision in {"provider_processed_with_artifact", "provider_processed_no_artifact"}:
        attempt.actual_cost_cents = float(getattr(attempt, "actual_cost_cents", 0.0) or 0.0) + reservation
        attempt.cost_source = "manual_reserved_estimate"
        operation.actual_provider_cost_cents = (
            float(getattr(operation, "actual_provider_cost_cents", 0.0) or 0.0) + reservation
        )
        metadata["manualReservedEstimateChargedCents"] = reservation
    else:
        metadata["manualReservedEstimateChargedCents"] = 0.0
    metadata["manualReconciliationDecision"] = decision
    attempt.outcome_metadata_json = metadata
    _settle_attempt_reservation(operation, attempt)


def normalize_operation_cost_limit(operation: InstantDeckOperation) -> bool:
    """Honor an operation's explicit cap; uncapped operations still track usage."""

    import math
    if operation.max_cost_cents is None:
        return False
    current_limit = float(operation.max_cost_cents)
    if not math.isfinite(current_limit) or current_limit <= 0:
        operation.status = "budget_exhausted"
        operation.terminal_reason = "provider_budget_invalid"
        raise InstantOperationBudgetExceeded("Instant Deck operation has an invalid provider budget.")
    committed_or_reserved = (
        float(getattr(operation, "actual_provider_cost_cents", 0.0) or 0.0)
        + float(getattr(operation, "reserved_provider_cost_cents", 0.0) or 0.0)
    )
    if committed_or_reserved > current_limit:
        operation.status = "budget_exhausted"
        operation.terminal_reason = "provider_budget_exhausted"
        raise InstantOperationBudgetExceeded("Instant Deck operation has already exceeded its provider budget.")
    return False


def canonical_request_hash(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def validate_durable_enqueue_feasibility(*, selected_slide_count: int) -> dict[str, int]:
    """Validate deterministic source bounds needed to persist deferred work."""
    if selected_slide_count <= 0 or selected_slide_count > FULL_HTML_MAX_SOURCE_SLIDES:
        raise InstantOperationConflict(
            f"Full HTML Instant Deck generation supports between 1 and {FULL_HTML_MAX_SOURCE_SLIDES} source slides."
        )
    estimated_output_bytes = 18_000 + selected_slide_count * 4_000
    return {"estimatedOutputBytes": estimated_output_bytes}


def validate_output_feasibility(*, selected_slide_count: int) -> dict[str, int]:
    """Validate mutable Instant runtime/provider/render output capability."""
    deterministic = validate_durable_enqueue_feasibility(selected_slide_count=selected_slide_count)
    if not settings.instant_html_enabled:
        raise InstantOperationConflict("Full HTML Instant Deck generation is disabled by configuration.")
    if not settings.instant_html_renderer_origin.strip():
        raise InstantOperationConflict("Full HTML Instant Deck rendering requires a dedicated renderer origin.")
    try:
        require_full_html_openai_model(settings.openai_model)
    except ValueError as exc:
        raise InstantOperationConflict(str(exc)) from exc
    if not 8_000 <= settings.instant_html_max_output_tokens <= FULL_HTML_MAX_OUTPUT_TOKENS:
        raise InstantOperationConflict("Full HTML output allowance must be between 8000 and 128000 tokens.")
    if settings.instant_html_max_provider_starts < MAX_PROVIDER_REQUEST_STARTS:
        raise InstantOperationConflict(
            "Full HTML provider start allowance must permit one generation and one bounded validation retry."
        )
    # A whole-deck response consolidates source material rather than emitting a
    # full independent document per input page. This reserves a polished CSS
    # and document shell plus a bounded context/output contribution per source.
    estimated_output_bytes = deterministic["estimatedOutputBytes"]
    capacity = settings.instant_html_whole_deck_max_bytes
    if estimated_output_bytes > capacity:
        raise InstantOperationConflict(
            f"A complete {selected_slide_count}-slide HTML deck exceeds the configured whole-deck HTML byte budget."
        )
    return {"estimatedOutputBytes": estimated_output_bytes, "outputCapacityBytes": capacity}


def resolve_operation(
    db: Session,
    *,
    deck_id: str,
    user_id: str,
    idempotency_key: str,
    request_payload: dict[str, Any],
) -> tuple[InstantDeckOperation, bool]:
    request_hash = canonical_request_hash(request_payload)
    existing = (
        db.query(InstantDeckOperation)
        .filter(
            InstantDeckOperation.deck_id == deck_id,
            InstantDeckOperation.user_id == user_id,
            InstantDeckOperation.idempotency_key == idempotency_key,
        )
        .with_for_update()
        .one_or_none()
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise InstantOperationConflict("The idempotency key is already bound to a different Instant Deck operation.")
        normalize_operation_cost_limit(existing)
        return existing, False
    active = (
        db.query(InstantDeckOperation)
        .filter(
            InstantDeckOperation.deck_id == deck_id,
            InstantDeckOperation.user_id == user_id,
            InstantDeckOperation.status.notin_({
                "completed",
                "failed_final",
                "budget_exhausted",
                "charge_failed",
            }),
        )
        .order_by(InstantDeckOperation.created_at.asc(), InstantDeckOperation.id.asc())
        .with_for_update()
        .first()
    )
    if active is not None:
        raise ActiveInstantOperationConflict(
            "An Instant Deck generation is already active for this deck. Reconcile it before regenerating."
        )
    operation = InstantDeckOperation(
        id=generate_id("instantop"),
        deck_id=deck_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status="enqueue_pending",
        output_contract="full_html_deck.v1",
        checkpoint_stage="operation_created",
        # Publisher-safe immutable policy ceilings. The Instant worker validates
        # current runtime configuration and narrows mutable allowances before charge.
        max_provider_request_starts=MAX_PROVIDER_REQUEST_STARTS,
        max_input_tokens=FULL_HTML_MAX_INPUT_TOKENS,
        max_output_tokens=FULL_HTML_MAX_OUTPUT_TOKENS,
        max_cost_cents=settings.instant_html_max_operation_cost_cents,
    )
    db.add(operation)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent request may have inserted the unique command after our
        # initial read. Re-read the winner and preserve request-hash binding.
        db.rollback()
        winner = db.query(InstantDeckOperation).filter(
            InstantDeckOperation.deck_id == deck_id,
            InstantDeckOperation.user_id == user_id,
            InstantDeckOperation.idempotency_key == idempotency_key,
        ).one()
        if winner.request_hash != request_hash:
            raise InstantOperationConflict("The idempotency key is already bound to a different Instant Deck operation.")
        normalize_operation_cost_limit(winner)
        return winner, False
    return operation, True


def _is_deferred_instant_worker_release(
    operation: InstantDeckOperation,
    workflow_job: WorkflowJob | None,
) -> bool:
    """Recognize the exact durable upload-first operation/job ownership contract."""
    workflow_input = (
        workflow_job.input_json
        if workflow_job is not None and isinstance(workflow_job.input_json, dict)
        else {}
    )
    return bool(
        operation.charge_status == "pending"
        and operation.status == "enqueue_pending"
        and workflow_job is not None
        and operation.workflow_job_id == workflow_job.id
        and workflow_job.job_type == "instant_deck_generation"
        and workflow_input.get("outputContract") == "full_html_deck.v1"
        and workflow_input.get("instantOperationId") == operation.id
        and workflow_input.get("providerReleaseOwner") == "instant_worker"
    )


def _require_charge_eligible(operation: InstantDeckOperation) -> None:
    if operation.status not in {
        "enqueue_pending",
        "charge_reconciling",
    } or operation.charge_status not in {"pending", "charging", "charged"}:
        raise InstantOperationConflict("A terminal or ineligible Instant Deck operation cannot be charged.")


def _lock_and_refresh_operation(db: Session, operation_id: str) -> InstantDeckOperation:
    operation = (
        db.query(InstantDeckOperation)
        .filter(InstantDeckOperation.id == operation_id)
        .with_for_update()
        .one()
    )
    db.refresh(operation)
    return operation


def _charge_eligible(operation: InstantDeckOperation) -> bool:
    try:
        _require_charge_eligible(operation)
    except InstantOperationConflict:
        return False
    return True


def _preserve_terminal_after_ledger_outcome(
    db: Session,
    operation: InstantDeckOperation,
    *,
    reservation_key: str,
    ledger_status: str | None,
) -> InstantDeckOperation:
    """Resolve quota state without changing an operation's terminal state.

    The caller holds the operation row lock. Cancellation is a cross-database
    ledger operation, so release that lock first and re-lock before recording
    its result.
    """
    if _charge_eligible(operation):
        raise RuntimeError("Terminal ledger cleanup requires an ineligible operation.")
    if ledger_status == "reserved":
        db.commit()
        released = cancel_ai_operation_budget(db, reservation_key=reservation_key)
        operation = _lock_and_refresh_operation(db, operation.id)
        operation.charge_status = "released" if released else "release_failed"
    elif ledger_status in {None, "cancelled"}:
        operation.charge_status = "released"
    else:
        # A reconciled debit is consumed and cannot be truthfully cancelled.
        operation.charge_status = "release_failed"
    db.commit()
    return operation


def charge_new_operation(
    db: Session,
    operation_id: str,
    user: User,
    *,
    locked_eligibility_validator: Callable[[Session, InstantDeckOperation, User], None] | None = None,
) -> InstantDeckOperation:
    """Idempotently reserve quota after operation identity exists.

    The reservation key is durable before the cross-database debit. A crash
    after debit is resolved by reading the same reservation, never by charging
    again or leaving an indefinite unknown state.
    """
    operation = _lock_and_refresh_operation(db, operation_id)
    try:
        normalized = normalize_operation_cost_limit(operation)
    except InstantOperationBudgetExceeded:
        db.commit()
        raise
    if normalized:
        db.flush()
    if (
        operation.status == "queued"
        and operation.charge_status == "charged"
        and int(operation.provider_request_starts or 0) == 0
    ):
        if locked_eligibility_validator is not None:
            locked_eligibility_validator(db, operation, user)
        return operation
    _require_charge_eligible(operation)
    if locked_eligibility_validator is not None:
        # This is the last core-DB transaction before the independent quota
        # reservation. All mutable eligibility and immutable bindings are
        # re-read under the operation lock here.
        locked_eligibility_validator(db, operation, user)
    if operation.charge_status == "charged":
        return operation
    reservation_key = operation.product_credit_transaction_id or f"instant-html:{operation.id}"
    operation.product_credit_transaction_id = reservation_key
    operation.charge_status = "charging"
    operation.status = "charge_reconciling"
    db.commit()
    reservation_status = ai_operation_budget_status(db, reservation_key=reservation_key)
    operation = _lock_and_refresh_operation(db, operation_id)
    if not _charge_eligible(operation):
        operation = _preserve_terminal_after_ledger_outcome(
            db,
            operation,
            reservation_key=reservation_key,
            ledger_status=reservation_status,
        )
        raise InstantOperationConflict("Instant Deck operation terminalized while its quota charge was resolving.")
    if reservation_status == "cancelled":
        operation.charge_status = "released"
        operation.status = "charge_failed"
        operation.terminal_reason = "quota_reservation_cancelled"
        db.commit()
        raise InstantOperationConflict("Instant Deck quota reservation was cancelled.")
    if reservation_status in {"reserved", "reconciled"}:
        operation.charge_status = "charged"
        operation.status = "enqueue_pending"
        operation.checkpoint_stage = "charge_confirmed"
        db.commit()
        return operation
    # Never hold the operation row lock while the quota database is called.
    db.commit()
    try:
        reserve_ai_operation_budget(
            db,
            user,
            operation="smart_deck_generation",
            reservation_key=reservation_key,
            estimated_tokens=min(200_000, operation.max_input_tokens + operation.max_output_tokens),
            daily_limit=settings.ai_daily_generation_quota,
        )
    except Exception:
        # The quota owner commits independently and can still raise during a
        # post-commit refresh. Inspect its durable truth before deciding that
        # the charge failed; do not hold the operation lock during that read.
        db.rollback()
        reservation_status = ai_operation_budget_status(db, reservation_key=reservation_key)
        operation = _lock_and_refresh_operation(db, operation_id)
        if not _charge_eligible(operation):
            _preserve_terminal_after_ledger_outcome(
                db,
                operation,
                reservation_key=reservation_key,
                ledger_status=reservation_status,
            )
            raise
        if reservation_status in {"reserved", "reconciled"}:
            # Durable ledger success wins over a post-commit caller exception.
            # This matches normal crash reconciliation and avoids charging the
            # user while leaving the operation falsely released.
            operation.charge_status = "charged"
            operation.status = "enqueue_pending"
            operation.checkpoint_stage = "charge_confirmed"
            db.commit()
            return operation
        operation.charge_status = "released"
        operation.status = "charge_failed"
        operation.terminal_reason = (
            "quota_reservation_cancelled"
            if reservation_status == "cancelled"
            else "product_quota_rejected"
        )
        db.commit()
        raise
    operation = _lock_and_refresh_operation(db, operation_id)
    if not _charge_eligible(operation):
        operation = _preserve_terminal_after_ledger_outcome(
            db,
            operation,
            reservation_key=reservation_key,
            ledger_status="reserved",
        )
        raise InstantOperationConflict("Instant Deck operation terminalized while its quota charge was resolving.")
    operation.charge_status = "charged"
    operation.status = "enqueue_pending"
    operation.checkpoint_stage = "charge_confirmed"
    db.commit()
    return operation


def reconcile_charging_operations(db: Session) -> int:
    """Resolve every post-debit crash from the durable reservation identity."""
    reconciled = 0
    operation_ids = [operation.id for operation in db.query(InstantDeckOperation).filter(
        InstantDeckOperation.charge_status.in_(["pending", "charging"])
    ).all()]
    db.commit()
    for operation_id in operation_ids:
        operation = db.query(InstantDeckOperation).filter(
            InstantDeckOperation.id == operation_id
        ).one_or_none()
        if operation is None:
            db.commit()
            continue
        workflow_job_id = getattr(operation, "workflow_job_id", None)
        workflow_job = (
            db.query(WorkflowJob).filter(WorkflowJob.id == workflow_job_id).one_or_none()
            if workflow_job_id
            else None
        )
        if operation.charge_status == "pending" and _is_deferred_instant_worker_release(operation, workflow_job):
            # This is a durable upload-first release, not a post-debit crash.
            # Only the provider-capable Instant worker may validate and charge it.
            db.commit()
            continue
        reservation_key = operation.product_credit_transaction_id or f"instant-html:{operation.id}"
        # Selection is intentionally unlocked. End its read transaction before
        # crossing into the independently durable quota ledger.
        db.commit()
        status = ai_operation_budget_status(db, reservation_key=reservation_key)
        current = _lock_and_refresh_operation(db, operation.id)
        if not _charge_eligible(current):
            _preserve_terminal_after_ledger_outcome(
                db,
                current,
                reservation_key=reservation_key,
                ledger_status=status,
            )
            continue
        if status in {"reserved", "reconciled"}:
            current.charge_status = "charged"
            current.status = "enqueue_pending"
            current.checkpoint_stage = "charge_confirmed"
            reconciled += 1
        elif status == "cancelled":
            current.charge_status = "released"
            current.status = "charge_failed"
            current.terminal_reason = "quota_reservation_cancelled"
        else:
            # Maintenance has no locked request-context eligibility validator.
            # A missing durable ledger row may be a legacy pre-validation
            # operation, so never create a fresh debit here. Hold it for manual
            # review and block the outbox from reaching provider release.
            current.charge_status = "held"
            current.status = "manual_reconciliation_required"
            current.checkpoint_stage = "charge_ledger_missing_manual_review"
            current.terminal_reason = "charge_ledger_missing"
            if workflow_job is not None and workflow_job.id == current.workflow_job_id:
                workflow_job.status = "blocked"
                workflow_job.terminal_reason = "charge_ledger_missing"
    db.commit()
    return reconciled


def confirm_operation_enqueued(db: Session, operation_id: str, workflow_job_id: str) -> InstantDeckOperation:
    """Durably bind the outbox job after a confirmed charge; safe on replay."""
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == operation_id).with_for_update().one()
    if operation.charge_status != "charged":
        raise InstantOperationConflict("Workflow enqueue is blocked until charge confirmation.")
    if operation.workflow_job_id not in {None, workflow_job_id}:
        raise InstantOperationConflict("Instant Deck operation is already bound to another workflow job.")
    operation.workflow_job_id = workflow_job_id
    workflow_job = db.query(WorkflowJob).filter(WorkflowJob.id == workflow_job_id).with_for_update().one()
    if workflow_job.status == "blocked":
        workflow_job.status = "queued"
    # Callback replay must not regress a running or terminal operation.
    if operation.status in {"enqueue_pending", "charge_reconciling"}:
        operation.status = "queued"
        operation.checkpoint_stage = "charged_and_enqueued"
    db.commit()
    return operation


def reconcile_enqueue_pending_operations(db: Session) -> int:
    """Repair charge/queue crashes without charging or starting provider work."""
    repaired = 0
    for operation in db.query(InstantDeckOperation).filter(InstantDeckOperation.status == "enqueue_pending").all():
        workflow_job = (
            db.query(WorkflowJob).filter(WorkflowJob.id == operation.workflow_job_id).one_or_none()
            if operation.workflow_job_id
            else None
        )
        if operation.charge_status == "charged" and operation.workflow_job_id:
            operation.status = "queued"
            operation.checkpoint_stage = "charged_and_enqueued"
            if workflow_job is not None and workflow_job.status == "blocked":
                workflow_job.status = "queued"
            repaired += 1
        elif operation.charge_status != "charged":
            # Upload-first jobs are intentionally queued while the durable
            # operation is still pending: the provider-capable Instant worker
            # owns provider validation and charge release. Manual commands
            # remain blocked and retain the existing reconciliation behavior.
            if _is_deferred_instant_worker_release(operation, workflow_job):
                continue
            operation.status = "charge_failed" if operation.charge_status == "released" else "charge_reconciling"
            if workflow_job is not None and workflow_job.status == "queued":
                workflow_job.status = "blocked"
    db.commit()
    return repaired


def start_provider_attempt(
    db: Session,
    operation_id: str,
    *,
    provider: str,
    model: str | None,
    request_kind: str,
    estimated_input_tokens: int = 0,
    max_output_tokens: int | None = None,
    client_request_id: str | None = None,
    request_context_hash: str | None = None,
    provider_binding_hash: str | None = None,
    request_envelope: dict[str, Any] | None = None,
    request_envelope_hash: str | None = None,
    validation_repair_metadata: dict[str, Any] | None = None,
    locked_prestart_binding: Callable[[Session, InstantDeckOperation], dict[str, Any]] | None = None,
) -> InstantDeckProviderAttempt:
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == operation_id).with_for_update().one()
    try:
        normalized = normalize_operation_cost_limit(operation)
    except InstantOperationBudgetExceeded:
        db.commit()
        raise
    if normalized:
        db.flush()
    if operation.status == "manual_reconciliation_required":
        raise InstantOperationConflict("Provider work is blocked pending manual reconciliation.")
    if operation.charge_status != "charged":
        raise InstantOperationConflict("Provider work is blocked until the operation charge is resolved.")
    if operation.provider_request_starts >= min(MAX_PROVIDER_REQUEST_STARTS, operation.max_provider_request_starts):
        raise InstantOperationBudgetExceeded("Instant Deck provider request-start budget is exhausted.")
    if operation.provider_request_starts == 0:
        if request_kind != "generation":
            raise InstantOperationConflict("The first provider request must be initial generation.")
    else:
        previous = db.query(InstantDeckProviderAttempt).filter(
            InstantDeckProviderAttempt.operation_id == operation.id,
            InstantDeckProviderAttempt.attempt_number == 1,
        ).one_or_none()
        if (
            request_kind != "deterministic_validation_retry"
            or previous is None
            or not previous.outcome_known
            or (previous.validation_summary_json or {}).get("status") != "failed"
        ):
            raise InstantOperationConflict("A second request requires a recorded compilation-validation failure.")
    output_allowance = int(max_output_tokens or operation.max_output_tokens)
    estimate = require_next_request_cost_budget(
        operation,
        provider=provider,
        model=model,
        estimated_input_tokens=estimated_input_tokens,
        max_output_tokens=output_allowance,
    )
    if locked_prestart_binding is not None:
        # Bind mutable source truth while the operation and source-owner rows
        # remain locked through durable attempt creation. Provider transport
        # starts only after the commit below releases every database lock.
        binding = locked_prestart_binding(db, operation)
        bound_hash = binding.get("bindingHash") if isinstance(binding, dict) else None
        if not isinstance(bound_hash, str) or not bound_hash:
            raise InstantOperationConflict("Provider source binding is unavailable.")
        if provider_binding_hash is not None and provider_binding_hash != bound_hash:
            raise InstantOperationConflict("Provider source binding changed before attempt start.")
        provider_binding_hash = bound_hash
    operation.provider_request_starts += 1
    operation.status = "provider_running"
    operation.checkpoint_stage = "provider_request_started"
    attempt = InstantDeckProviderAttempt(
        id=generate_id("instantattempt"),
        operation_id=operation.id,
        attempt_number=operation.provider_request_starts,
        request_kind=request_kind,
        provider=provider,
        model=model,
        outcome_known=False,
        response_state="started",
        provider_idempotency_key=None,
        client_request_id=client_request_id or str(uuid4()),
        reserved_cost_cents=estimate,
        outcome_metadata_json={
            **({"requestContextHash": request_context_hash} if request_context_hash else {}),
            **({"providerBindingHash": provider_binding_hash} if provider_binding_hash else {}),
            **({"requestEnvelope": request_envelope} if request_envelope else {}),
            **({"requestEnvelopeHash": request_envelope_hash} if request_envelope_hash else {}),
            **({"validationRepair": validation_repair_metadata} if validation_repair_metadata else {}),
        } or None,
    )
    operation.reserved_provider_cost_cents = float(getattr(operation, "reserved_provider_cost_cents", 0.0) or 0.0) + estimate
    db.add(attempt)
    db.commit()
    return attempt


def provider_supports_idempotent_replay(provider: str) -> bool:
    # No supported full-HTML POST transport has an officially documented
    # deduplication guarantee. A client request ID is support correlation only.
    return False


def resume_unknown_provider_attempt(
    db: Session,
    attempt_id: str,
    *,
    provider: str,
    model: str | None,
) -> InstantDeckProviderAttempt:
    attempt = db.query(InstantDeckProviderAttempt).filter(
        InstantDeckProviderAttempt.id == attempt_id
    ).with_for_update().one()
    operation = db.query(InstantDeckOperation).filter(
        InstantDeckOperation.id == attempt.operation_id
    ).with_for_update().one()
    if operation.charge_status != "charged":
        raise InstantOperationConflict("Provider reconciliation is blocked until charge confirmation.")
    if attempt.outcome_known or attempt.raw_artifact_id:
        raise InstantOperationConflict("Provider attempt no longer has an unknown outcome.")
    if attempt.provider != provider or attempt.model != model:
        raise InstantOperationConflict("Unknown provider attempt identity does not match reconciliation request.")
    if not provider_supports_idempotent_replay(provider):
        operation.status = "manual_reconciliation_required"
        operation.charge_status = "held"
        operation.checkpoint_stage = "provider_outcome_unknown"
        if getattr(operation, "workflow_job_id", None):
            job = db.query(WorkflowJob).filter(WorkflowJob.id == operation.workflow_job_id).with_for_update().one_or_none()
            if job is not None:
                job.status = "blocked"
                job.terminal_reason = "provider_manual_reconciliation"
        db.commit()
        raise InstantOperationConflict("Provider does not support safe idempotent replay; manual reconciliation is required.")
    attempt.response_state = "reconciling_same_identity"
    attempt.response_received_at = None
    operation.status = "provider_reconciling"
    operation.checkpoint_stage = "provider_reconciling_same_identity"
    db.commit()
    return attempt


def finish_provider_attempt(
    db: Session,
    attempt_id: str,
    *,
    response_state: str,
    outcome_known: bool,
    provider_request_id: str | None = None,
    provider_response_id: str | None = None,
    usage: dict[str, Any] | None = None,
    http_status: int | None = None,
    provider_error_code: str | None = None,
    retry_after_seconds: float | None = None,
    rate_limit_metadata: dict[str, Any] | None = None,
    outcome_metadata: dict[str, Any] | None = None,
) -> InstantDeckProviderAttempt:
    attempt = db.query(InstantDeckProviderAttempt).filter(InstantDeckProviderAttempt.id == attempt_id).with_for_update().one()
    if attempt.response_received_at is not None and attempt.outcome_known:
        operation = db.query(InstantDeckOperation).filter(
            InstantDeckOperation.id == attempt.operation_id
        ).with_for_update().one()
        if _settle_attempt_reservation(operation, attempt):
            db.commit()
        return attempt
    usage = usage or {}
    attempt.provider_request_id = provider_request_id
    attempt.provider_response_id = provider_response_id
    attempt.http_status = http_status
    if provider_error_code is not None:
        from app.services.llm.openai_provider import _redacted_provider_code

        provider_error_code = _redacted_provider_code(provider_error_code)
    attempt.provider_error_code = provider_error_code
    attempt.retry_after_seconds = retry_after_seconds
    attempt.rate_limit_metadata_json = dict(rate_limit_metadata or {})
    existing_metadata = dict(getattr(attempt, "outcome_metadata_json", None) or {})
    attempt.outcome_metadata_json = {**existing_metadata, **dict(outcome_metadata or {})}
    attempt.response_received_at = datetime.utcnow()
    attempt.outcome_known = outcome_known
    attempt.response_state = response_state
    attempt.actual_input_tokens = max(0, int(usage.get("input_tokens") or usage.get("inputTokens") or usage.get("prompt_tokens") or 0))
    attempt.actual_output_tokens = max(0, int(usage.get("output_tokens") or usage.get("outputTokens") or usage.get("completion_tokens") or 0))
    supplied_cost = usage.get("actual_cost_cents")
    cost_source = "actual"
    if supplied_cost is None:
        supplied_cost = usage.get("estimated_cost_cents")
        if supplied_cost is None:
            supplied_cost = estimate_model_cost_cents(
                attempt.provider,
                attempt.model,
                input_tokens=attempt.actual_input_tokens,
                output_tokens=attempt.actual_output_tokens,
            )
        cost_source = str(usage.get("cost_source") or "estimated") if supplied_cost is not None else "unknown"
    attempt.actual_cost_cents = max(0.0, float(supplied_cost or 0.0))
    attempt.cost_source = cost_source
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == attempt.operation_id).with_for_update().one()
    operation.actual_input_tokens += attempt.actual_input_tokens
    operation.actual_output_tokens += attempt.actual_output_tokens
    operation.actual_provider_cost_cents += attempt.actual_cost_cents
    if outcome_known:
        _settle_attempt_reservation(operation, attempt)
    operation.checkpoint_stage = "provider_response_recorded" if outcome_known else "provider_outcome_unknown"
    if not outcome_known and not provider_supports_idempotent_replay(attempt.provider):
        operation.status = "manual_reconciliation_required"
        operation.charge_status = "held"
        if getattr(operation, "workflow_job_id", None):
            job = db.query(WorkflowJob).filter(WorkflowJob.id == operation.workflow_job_id).with_for_update().one_or_none()
            if job is not None:
                job.status = "blocked"
                job.terminal_reason = "provider_manual_reconciliation"
    if operation.max_cost_cents is not None and operation.actual_provider_cost_cents > operation.max_cost_cents:
        operation.status = "budget_exhausted"
        operation.terminal_reason = "provider_budget_exhausted"
    try:
        from app.services.ai_vc.observability import refresh_operation_usage_trace

        refresh_operation_usage_trace(
            db, deck_id=operation.deck_id, operation_id=operation.id,
        )
    except Exception:
        # Accounting settlement remains authoritative even if an advisory
        # diagnostic artifact cannot be refreshed in this transaction.
        pass
    db.commit()
    return attempt


def store_raw_checkpoint(db: Session, attempt_id: str, raw_output: str, *, retention_days: int = 7) -> InstantDeckHtmlArtifact:
    attempt = db.query(InstantDeckProviderAttempt).filter(InstantDeckProviderAttempt.id == attempt_id).with_for_update().one()
    if attempt.raw_artifact_id:
        return db.query(InstantDeckHtmlArtifact).filter(InstantDeckHtmlArtifact.id == attempt.raw_artifact_id).one()
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == attempt.operation_id).one()
    raw = raw_output.encode("utf-8")
    digest = sha256(raw).hexdigest()
    encrypted = get_instant_html_raw_checkpoint_fernet().encrypt(raw)
    artifact_id = "deckhtml_" + sha256(
        f"raw:{operation.id}:{attempt.id}:{digest}:{RAW_CHECKPOINT_ENCRYPTION_PURPOSE}".encode("utf-8")
    ).hexdigest()[:24]
    storage_key = f"decks/{operation.deck_id}/instant-deck-operations/{operation.id}/attempts/{attempt.id}/quarantine/{artifact_id}.bin"
    register_artifact_cleanup_tasks(
        db, deck_id=operation.deck_id, operation_id=operation.id,
        attempt_id=attempt.id, storage_keys=[storage_key],
    )
    db.expire_all()
    attempt = db.query(InstantDeckProviderAttempt).filter(
        InstantDeckProviderAttempt.id == attempt_id
    ).with_for_update().one()
    operation = db.query(InstantDeckOperation).filter(
        InstantDeckOperation.id == attempt.operation_id
    ).with_for_update().one()
    if attempt.raw_artifact_id:
        existing = db.query(InstantDeckHtmlArtifact).filter(
            InstantDeckHtmlArtifact.id == attempt.raw_artifact_id
        ).one()
        if (
            existing.id != artifact_id or existing.storage_key != storage_key
            or existing.content_hash != digest or existing.operation_id != operation.id
            or existing.provider_attempt_id != attempt.id
            or existing.deck_id != operation.deck_id or existing.artifact_kind != "raw"
            or int(existing.byte_size or 0) != len(raw) or not existing.quarantined
            or not existing.encrypted
            or existing.encryption_key_version != settings.workspace_ai_fernet_key_version
            or existing.encryption_purpose != RAW_CHECKPOINT_ENCRYPTION_PURPOSE
        ):
            raise RuntimeError("Existing raw checkpoint identity conflicts with the deterministic write plan.")
        complete_artifact_cleanup_tasks(db, [storage_key])
        db.commit()
        return existing
    require_staged_cleanup_tasks(db, [storage_key])
    storage = get_upload_storage()
    promote_upload(storage.write_bytes(storage_key, encrypted))
    artifact = InstantDeckHtmlArtifact(
        id=artifact_id,
        deck_id=operation.deck_id,
        operation_id=operation.id,
        provider_attempt_id=attempt.id,
        artifact_kind="raw",
        storage_key=storage_key,
        content_hash=digest,
        byte_size=len(raw),
        quarantined=True,
        encrypted=True,
        encryption_key_version=settings.workspace_ai_fernet_key_version,
        encryption_purpose=RAW_CHECKPOINT_ENCRYPTION_PURPOSE,
        retention_expires_at=datetime.utcnow() + timedelta(days=retention_days),
    )
    db.add(artifact)
    db.flush()
    db.add(SecurityAuditEvent(
        id=generate_id("audit"), actor_user_id=None, action="instant_html.raw_checkpoint.write",
        resource_type="instant_deck_html_artifact", resource_id=artifact.id, result="success",
        details_json={"operationId": operation.id, "attemptId": attempt.id, "contentHash": digest},
    ))
    attempt.raw_artifact_id = artifact.id
    operation.checkpoint_stage = "raw_artifact_stored"
    complete_artifact_cleanup_tasks(db, [storage_key])
    db.commit()
    return artifact


def purge_expired_raw_artifacts(db: Session, *, now: datetime | None = None) -> int:
    """Idempotently purge expired encrypted private artifacts from storage and DB."""
    now = now or datetime.utcnow()
    stale_claim_before = now - CLEANUP_TASK_STALE_AFTER
    storage = get_upload_storage()
    purged = 0
    artifacts = db.query(InstantDeckHtmlArtifact).filter(
        InstantDeckHtmlArtifact.artifact_kind.in_(["raw", "request_context"]),
        InstantDeckHtmlArtifact.quarantined.is_(True),
        or_(
            and_(
                InstantDeckHtmlArtifact.retention_expires_at <= now,
                or_(
                    InstantDeckHtmlArtifact.purge_status.is_(None),
                    InstantDeckHtmlArtifact.purge_status == "retry_pending",
                ),
            ),
            InstantDeckHtmlArtifact.purge_status.in_(["rotation_pending_delete", "rotation_retry_pending"]),
            and_(
                InstantDeckHtmlArtifact.purge_status.in_(["deleting", "rotation_deleting"]),
                InstantDeckHtmlArtifact.purge_error_at <= stale_claim_before,
            ),
        ),
    ).with_for_update(skip_locked=True).limit(100).all()
    claimed_artifacts: list[tuple[str, bool, str]] = []

    def request_context_terminal_safe(operation: InstantDeckOperation | None) -> bool:
        terminal_at = operation.completed_at if operation is not None else None
        return bool(
            operation is not None
            and operation.status in {"failed_final", "completed"}
            and terminal_at is not None
            and terminal_at + REQUEST_CONTEXT_TERMINAL_RETENTION <= now
        )

    for artifact in artifacts:
        if artifact.artifact_kind == "request_context":
            operation = db.query(InstantDeckOperation).filter(
                InstantDeckOperation.id == artifact.operation_id
            ).with_for_update().one_or_none()
            if not request_context_terminal_safe(operation):
                # Active/blocked/reconciling work retains its exact context even
                # when the initial wall-clock retention date passes.
                continue
        rotation_cleanup = artifact.purge_status in {
            "rotation_pending_delete", "rotation_retry_pending", "rotation_deleting"
        }
        claimed_status = "rotation_deleting" if rotation_cleanup else "deleting"
        claimed_artifacts.append((artifact.id, rotation_cleanup, claimed_status))
        artifact.purge_attempts = int(artifact.purge_attempts or 0) + 1
        artifact.purge_status = claimed_status
        artifact.purge_error_at = now
    db.commit()
    for artifact_id, rotation_cleanup, claimed_status in claimed_artifacts:
        artifact = db.query(InstantDeckHtmlArtifact).filter(
            InstantDeckHtmlArtifact.id == artifact_id,
            InstantDeckHtmlArtifact.purge_status == claimed_status,
        ).with_for_update().one_or_none()
        if artifact is None:
            continue
        if artifact.artifact_kind == "request_context":
            # The claim transaction intentionally releases locks between batch
            # selection and I/O. Re-lock both owners and repeat lifecycle
            # eligibility immediately before deletion so a recovery transition
            # cannot lose its resumable encrypted context.
            operation = db.query(InstantDeckOperation).filter(
                InstantDeckOperation.id == artifact.operation_id
            ).with_for_update().one_or_none()
            if not request_context_terminal_safe(operation):
                artifact.purge_status = (
                    "rotation_retry_pending" if rotation_cleanup else "retry_pending"
                )
                artifact.purge_error_at = now
                db.commit()
                continue
        audit_action = (
            "instant_html.request_context.purge"
            if artifact.artifact_kind == "request_context"
            else "instant_html.raw_checkpoint.purge"
        )
        try:
            storage.delete(artifact.storage_key)
            if storage.object_exists(artifact.storage_key):
                raise RuntimeError("Artifact still exists after delete confirmation")
        except Exception:
            artifact.purge_status = "rotation_retry_pending" if rotation_cleanup else "retry_pending"
            artifact.purge_error_at = now
            db.add(SecurityAuditEvent(
                id=generate_id("audit"), actor_user_id=None, action=audit_action,
                resource_type="instant_deck_html_artifact", resource_id=artifact.id, result="failure",
                details_json={"operationId": artifact.operation_id, "attempt": artifact.purge_attempts},
            ))
            db.commit()
            continue
        db.add(SecurityAuditEvent(
            id=generate_id("audit"), actor_user_id=None, action=audit_action,
            resource_type="instant_deck_html_artifact", resource_id=artifact.id, result="success",
            details_json={"operationId": artifact.operation_id, "contentHash": artifact.content_hash},
        ))
        db.delete(artifact)
        purged += 1
        db.commit()
    # Expired capabilities contain no plaintext token, but deleting them keeps
    # the public-auth table bounded. Revoked rows are retained until expiry.
    db.query(InstantDeckRenderCapability).filter(InstantDeckRenderCapability.expires_at <= now).delete(synchronize_session=False)
    db.commit()
    return purged


def _mark_terminal_locked(
    db: Session,
    operation: InstantDeckOperation,
    *,
    reason: str,
    valid_artifact: bool,
    defer_release: bool = False,
) -> InstantDeckOperation:
    operation.status = "artifact_ready" if valid_artifact else "failed_final"
    operation.terminal_reason = None if valid_artifact else reason
    operation.completed_at = None if valid_artifact else datetime.utcnow()
    operation.checkpoint_stage = "artifact_ready" if valid_artifact else "failed_final"
    if not valid_artifact and operation.workflow_job_id:
        workflow_job = db.query(WorkflowJob).filter(
            WorkflowJob.id == operation.workflow_job_id,
            WorkflowJob.deck_id == operation.deck_id,
        ).with_for_update().one_or_none()
        # A downstream render failure terminalizes the operation but must not
        # rewrite an already completed generation root. Only align roots that
        # failed while generation itself was still active.
        if workflow_job is not None and workflow_job.status != "completed":
            workflow_job.status = "failed_final"
            workflow_job.error_code = reason
            workflow_job.error_message = INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE
            workflow_job.terminal_reason = reason
            workflow_job.failed_at = datetime.utcnow()
            workflow_job.locked_by = None
            workflow_job.locked_until = None
        if workflow_job is None or workflow_job.status != "completed":
            generation_job = db.query(GenerationJob).filter(
                GenerationJob.id == operation.workflow_job_id,
                GenerationJob.deck_id == operation.deck_id,
            ).with_for_update().one_or_none()
            if generation_job is not None:
                generation_job.status = "failed"
                generation_job.error_message = INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE
                generation_job.completed_at = datetime.utcnow()
    if not valid_artifact and operation.charge_status in {"charged", "held"}:
        reservation_key = str(operation.product_credit_transaction_id or f"instant-html:{operation.id}")
        operation.charge_status = "release_pending"
        db.commit()
        if defer_release or _is_preview_render_runtime():
            return operation
        try:
            released = cancel_ai_operation_budget(db, reservation_key=reservation_key)
        except (ProgrammingError, OperationalError):
            db.rollback()
            operation = _lock_and_refresh_operation(db, operation.id)
            operation.charge_status = "release_pending"
            db.commit()
            return operation
        operation = _lock_and_refresh_operation(db, operation.id)
        # The external cancellation result updates accounting only. A
        # concurrent terminal reason/stage remains authoritative.
        operation.charge_status = "released" if released else "release_failed"
    db.commit()
    return operation


def mark_terminal(db: Session, operation_id: str, *, reason: str, valid_artifact: bool) -> InstantDeckOperation:
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == operation_id).with_for_update().one()
    return _mark_terminal_locked(db, operation, reason=reason, valid_artifact=valid_artifact)


def terminalize_generation_failure(
    db: Session,
    *,
    reason: str,
    operation_id: str | None = None,
    workflow_job_id: str | None = None,
    defer_release: bool = False,
) -> InstantDeckOperation | None:
    """Idempotently fail an existing Instant operation and release its quota.

    Looking up by workflow identity lets the production worker cover failures
    before request payload/provider/context setup succeeds. Absence is a no-op:
    this helper never creates or terminalizes an operation that does not exist.
    """
    if not operation_id and not workflow_job_id:
        raise ValueError("Instant operation or workflow identity is required.")
    query = db.query(InstantDeckOperation)
    if operation_id:
        query = query.filter(InstantDeckOperation.id == operation_id)
    else:
        query = query.filter(InstantDeckOperation.workflow_job_id == workflow_job_id)
    operation = query.with_for_update().one_or_none()
    if operation is None:
        return operation
    if operation.status == "failed_final":
        # Repair older partial terminalization so the customer read model does
        # not expose a permanently queued GenerationJob after the authoritative
        # workflow and operation have failed.
        generation_job = db.query(GenerationJob).filter(
            GenerationJob.id == operation.workflow_job_id,
            GenerationJob.deck_id == operation.deck_id,
        ).with_for_update().one_or_none()
        if generation_job is not None and generation_job.status in {"queued", "running"}:
            generation_job.status = "failed"
            generation_job.error_message = INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE
            generation_job.completed_at = operation.completed_at or datetime.utcnow()
            db.commit()
        return operation
    if operation.status == "completed":
        return operation
    if (
        reason in {"generation_processing_failed", "generation_artifact_recording_failed"}
        and int(operation.provider_request_starts or 0) == 0
        and not db.query(InstantDeckProviderAttempt).filter(
            InstantDeckProviderAttempt.operation_id == operation.id,
        ).first()
    ):
        operation.status = "queued"
        operation.terminal_reason = None
        operation.checkpoint_stage = "pre_provider_retryable"
        db.commit()
        return operation
    return _mark_terminal_locked(
        db,
        operation,
        reason=reason,
        valid_artifact=False,
        defer_release=defer_release,
    )


def resolve_manual_provider_attempt(
    db: Session,
    attempt_id: str,
    *,
    decision: str,
    actor_user_id: str | None = None,
    raw_output: str | None = None,
) -> InstantDeckOperation:
    """Consume a non-replayable unknown outcome without a public product route."""
    allowed = {"provider_not_processed", "provider_processed_with_artifact", "provider_processed_no_artifact"}
    if decision not in allowed:
        raise InstantOperationConflict("Unknown manual provider reconciliation decision.")
    attempt = db.query(InstantDeckProviderAttempt).filter(InstantDeckProviderAttempt.id == attempt_id).with_for_update().one()
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == attempt.operation_id).with_for_update().one()
    metadata = dict(getattr(attempt, "outcome_metadata_json", None) or {})
    if attempt.outcome_known and metadata.get("manualReconciliationDecision") == decision:
        return operation
    if operation.status != "manual_reconciliation_required" or attempt.outcome_known:
        raise InstantOperationConflict("Provider attempt is not awaiting manual reconciliation.")
    if decision == "provider_processed_with_artifact":
        if not raw_output or not raw_output.strip():
            raise InstantOperationConflict("A provider artifact is required for this reconciliation decision.")
        store_raw_checkpoint(db, attempt.id, raw_output)
        attempt = db.query(InstantDeckProviderAttempt).filter(InstantDeckProviderAttempt.id == attempt_id).with_for_update().one()
        operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == attempt.operation_id).with_for_update().one()
        attempt.outcome_known = True
        attempt.response_state = decision
        attempt.response_received_at = datetime.utcnow()
        operation.status = "provider_checkpoint_ready"
        operation.charge_status = "charged"
        operation.checkpoint_stage = "raw_artifact_stored"
        if operation.workflow_job_id:
            job = db.query(WorkflowJob).filter(WorkflowJob.id == operation.workflow_job_id).with_for_update().one_or_none()
            if job is not None:
                job.status = "queued"
                job.locked_by = None
                job.locked_until = None
                job.error_code = None
                job.error_message = None
    else:
        attempt.outcome_known = True
        attempt.response_state = decision
        attempt.response_received_at = datetime.utcnow()
        operation.terminal_reason = decision
    _reconcile_manual_attempt_cost(operation, attempt, decision=decision)
    db.add(SecurityAuditEvent(
        id=generate_id("audit"), actor_user_id=actor_user_id,
        action="instant_html.provider_attempt.reconcile", resource_type="instant_deck_provider_attempt",
        resource_id=attempt.id, result="success", details_json={"operationId": operation.id, "decision": decision},
    ))
    db.commit()
    if decision != "provider_processed_with_artifact":
        return mark_terminal(db, operation.id, reason=decision, valid_artifact=False)
    return operation


def reconcile_expired_manual_provider_operations(db: Session, *, now: datetime | None = None) -> int:
    """Fail safe after the operator window: terminalize and release held quota."""
    cutoff = (now or datetime.utcnow()) - MANUAL_RECONCILIATION_MAX_AGE
    attempts = db.query(InstantDeckProviderAttempt).join(
        InstantDeckOperation, InstantDeckOperation.id == InstantDeckProviderAttempt.operation_id
    ).filter(
        InstantDeckOperation.status == "manual_reconciliation_required",
        InstantDeckOperation.updated_at <= cutoff,
        InstantDeckProviderAttempt.outcome_known.is_(False),
    ).all()
    for attempt in attempts:
        resolve_manual_provider_attempt(db, attempt.id, decision="provider_processed_no_artifact")
    return len(attempts)


def reconcile_release_pending_operations(db: Session) -> int:
    reconciled = 0
    operations = db.query(InstantDeckOperation).filter(
        InstantDeckOperation.charge_status == "release_pending"
    ).all()
    for operation in operations:
        reservation_key = str(operation.product_credit_transaction_id or f"instant-html:{operation.id}")
        operation_id = operation.id
        db.commit()
        status = ai_operation_budget_status(db, reservation_key=reservation_key)
        operation = _lock_and_refresh_operation(db, operation_id)
        if status == "reserved":
            db.commit()
            released = cancel_ai_operation_budget(db, reservation_key=reservation_key)
            operation = _lock_and_refresh_operation(db, operation_id)
            operation.charge_status = "released" if released else "release_failed"
        elif status in {None, "cancelled"}:
            operation.charge_status = "released"
        elif status == "reconciled":
            operation.charge_status = "release_failed"
        reconciled += 1
    db.commit()
    return reconciled


def mark_operation_published(db: Session, design_version_id: str) -> InstantDeckOperation | None:
    """Complete only after render proof and authoritative publisher success."""
    operation = db.query(InstantDeckOperation).filter(
        InstantDeckOperation.design_version_id == design_version_id
    ).with_for_update().one_or_none()
    if operation is None:
        return None
    if operation.status not in {"artifact_ready", "completed"}:
        raise InstantOperationConflict("Instant HTML operation is not ready for publication completion.")
    reservation_key = str(operation.product_credit_transaction_id or f"instant-html:{operation.id}")
    if operation.charge_status == RECOVERY_CREDIT_WAIVER_STATUS:
        compilation = db.query(InstantDeckCompilation).filter(
            InstantDeckCompilation.design_version_id == design_version_id,
            InstantDeckCompilation.deck_id == operation.deck_id,
        ).one_or_none()
        attempt = (
            db.query(InstantDeckProviderAttempt).filter(
                InstantDeckProviderAttempt.id == compilation.provider_attempt_id,
                InstantDeckProviderAttempt.operation_id == operation.id,
            ).one_or_none()
            if compilation is not None
            else None
        )
        recovery = (
            (attempt.outcome_metadata_json or {}).get("checkpointRecovery")
            if attempt is not None and isinstance(attempt.outcome_metadata_json, dict)
            else None
        )
        disposition = (
            (attempt.outcome_metadata_json or {}).get("recoveryBillingDisposition")
            if attempt is not None and isinstance(attempt.outcome_metadata_json, dict)
            else None
        )
        try:
            from app.services.llm.full_html_generation_service import (
                InstantHtmlCheckpointRecoveryError,
                LEGACY_BREAK_GLASS_DISPOSITION,
                validate_committed_publisher_recovery_lineage,
                validate_committed_recovery_lineage,
            )

            attestation = (
                (attempt.outcome_metadata_json or {}).get(
                    "publisherRecoveryAttestation"
                )
                if attempt is not None
                and isinstance(attempt.outcome_metadata_json, dict)
                else None
            )
            if (
                isinstance(recovery, dict)
                and recovery.get("contextDisposition") == LEGACY_BREAK_GLASS_DISPOSITION
            ):
                validate_committed_recovery_lineage(
                    db, operation=operation, design_version_id=design_version_id,
                )
            elif isinstance(attestation, dict):
                validate_committed_publisher_recovery_lineage(
                    db, operation=operation, design_version_id=design_version_id,
                )
            else:
                validate_committed_recovery_lineage(
                    db, operation=operation, design_version_id=design_version_id,
                )
        except InstantHtmlCheckpointRecoveryError as exc:
            raise InstantOperationConflict(
                "Recovered publication lacks exact current provider binding and committed lineage."
            ) from exc
        if (
            operation.checkpoint_stage not in {"recovered_artifact_ready", "published"}
            or compilation is None
            or attempt is None
            or not isinstance(recovery, dict)
            or recovery.get("designVersionId") != design_version_id
            or recovery.get("providerAttemptId") != attempt.id
            or recovery.get("compilerVersion") != compilation.compiler_version
            or recovery.get("creditWaiverReason") != RECOVERY_CREDIT_WAIVER_REASON
            or not isinstance(disposition, dict)
            or disposition.get("state") != RECOVERY_CREDIT_WAIVER_STATUS
            or disposition.get("productCreditReconsumed") is not False
        ):
            raise InstantOperationConflict("Recovered publication lacks exact durable credit-waiver lineage.")
        db.add(SecurityAuditEvent(
            id=generate_id("audit"), actor_user_id=None,
            action="instant_html.recovery_credit_waiver.published",
            resource_type="instant_deck_operation", resource_id=operation.id, result="success",
            details_json={
                "designVersionId": design_version_id,
                "providerAttemptId": attempt.id,
                "compilerVersion": compilation.compiler_version,
                "creditWaiverReason": RECOVERY_CREDIT_WAIVER_REASON,
                "providerCallExecuted": False,
            },
        ))
    elif operation.charge_status == 'review_recovery_waived':
        from app.services.llm.instant_factual_review import require_review_resume_lineage
        compilation = db.query(InstantDeckCompilation).filter_by(design_version_id=design_version_id, deck_id=operation.deck_id).one()
        continuation = require_review_resume_lineage(db, operation, compilation_hash=compilation.content_hash)
        continuation.status = 'completed'
    elif operation.charge_status != "charged":
        raise InstantOperationConflict("Publication requires a charged operation or exact recovery credit waiver.")
    if operation.status == "completed":
        return operation
    operation.status = "completed"
    operation.checkpoint_stage = "published"
    operation.completed_at = datetime.utcnow()
    if operation.charge_status not in {RECOVERY_CREDIT_WAIVER_STATUS, "review_recovery_waived"}:
        operation.charge_status = "consumed"
        reconcile_ai_operation_budget(
            db,
            reservation_key=reservation_key,
            actual_tokens=operation.actual_input_tokens + operation.actual_output_tokens,
        )
    return operation


def mark_render_recovery_proven(
    db: Session,
    design_version_id: str,
) -> InstantDeckOperation | None:
    """Advance only a waived render retry after its exact proofs are durable."""
    operation = db.query(InstantDeckOperation).filter(
        InstantDeckOperation.design_version_id == design_version_id
    ).with_for_update().one_or_none()
    if operation is None:
        return None
    if (
        operation.status != "artifact_ready"
        or operation.charge_status != RECOVERY_CREDIT_WAIVER_STATUS
        or operation.checkpoint_stage != "render_proof_retry_queued"
    ):
        return operation
    from app.db.models import DesignVersion
    from app.services.rendering.render_proof_service import require_complete_render_proofs

    version = db.query(DesignVersion).filter(
        DesignVersion.id == design_version_id,
        DesignVersion.deck_id == operation.deck_id,
    ).one_or_none()
    if version is None:
        raise InstantOperationConflict("Recovered render proof DesignVersion is missing.")
    require_complete_render_proofs(version, db)
    from app.services.llm.full_html_generation_service import (
        record_publisher_recovery_attestation,
    )

    generation_metadata = version.generation_job.llm_context_json
    if (
        isinstance(generation_metadata, dict)
        and all(
            generation_metadata.get(key)
            for key in (
                "fullHtmlRequestContextArtifactId",
                "fullHtmlRequestContextHash",
                "fullHtmlRequestBinding",
                "fullHtmlProviderBinding",
            )
        )
    ):
        record_publisher_recovery_attestation(
            db,
            operation=operation,
            design_version_id=design_version_id,
        )
    operation.checkpoint_stage = "recovered_artifact_ready"
    return operation


def terminalize_operation_for_design_version(
    db: Session,
    design_version_id: str,
    *,
    reason: str,
    defer_release: bool = False,
) -> InstantDeckOperation | None:
    operation = db.query(InstantDeckOperation).filter(
        InstantDeckOperation.design_version_id == design_version_id
    ).one_or_none()
    if operation is None:
        return operation
    return terminalize_generation_failure(
        db,
        operation_id=operation.id,
        reason=reason,
        defer_release=defer_release,
    )


def terminalize_operation_for_workflow_job(db: Session, workflow_job_id: str, *, reason: str) -> InstantDeckOperation | None:
    return terminalize_generation_failure(db, workflow_job_id=workflow_job_id, reason=reason)


def terminalize_operation_by_id(
    db: Session,
    operation_id: str,
    *,
    reason: str,
    defer_release: bool = False,
) -> InstantDeckOperation:
    operation = terminalize_generation_failure(
        db,
        operation_id=operation_id,
        reason=reason,
        defer_release=defer_release,
    )
    if operation is None:
        raise InstantOperationConflict("Instant HTML operation was not found.")
    return operation
    require_full_html_openai_model(settings.openai_model)
    if settings.instant_html_max_output_tokens > FULL_HTML_MAX_OUTPUT_TOKENS:
        raise InstantOperationConflict("Full HTML output allowance exceeds the OpenAI model limit.")
