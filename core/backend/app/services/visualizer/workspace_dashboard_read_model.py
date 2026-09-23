from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, selectinload

from app.db.models import AuditLog, Deck, DeckLlmArtifact, DeckSlide, DesignBatch, User, Workspace
from app.services.deck_processing.state_machine import canonical_deck_state
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state

AUDIENCE_DILIGENCE_ARTIFACT_TYPE = "audience_diligence_conversion_plan"


def _deck_status(status: str) -> str:
    state = canonical_deck_state(status).value
    if state in {"pending", "uploaded", "processing"}:
        return "preparing"
    if state == "ready":
        return "ready_to_review"
    if state == "failed":
        return "failed"
    return "preparing"


def _dashboard_deck_status(db: Session, deck: Deck | None) -> str:
    if deck is None:
        return "preparing"
    workflow = get_deck_workflow_state(db, deck.id)
    if workflow is None:
        return _deck_status(deck.status)
    phase = str(workflow.get("phase") or "")
    status = str(workflow.get("status") or "")
    if status in {"failed_retryable", "failed_final", "blocked", "timed_out"}:
        return "failed"
    source_file = getattr(deck, "file", None)
    instant_upload = bool(source_file and (source_file.metadata_json or {}).get("preferredWorkspace") == "instant_deck")
    if instant_upload or workflow.get("authoritativeInstantChain"):
        # Source publication permits Smart Deck access before any generated
        # version exists. Only canonical publication makes Instant slides ready.
        return "ready_to_review" if workflow.get("canOpenInstantDeck") else "preparing"
    if workflow.get("canOpenSmartDeck") or phase in {"smart_deck_ready", "preview_ready", "applied", "export_ready"}:
        return "ready_to_review"
    if phase in {"upload_accepted", "source_file_saved"}:
        return "preparing"
    if workflow.get("activeJob") or workflow.get("latestJobs"):
        return "preparing"
    return _deck_status(deck.status)


def _iteration_status(status: str) -> str:
    if status == "completed":
        return "ready_for_review"
    if status == "reviewed":
        return "accepted"
    if status == "compiled":
        return "compiled"
    if status == "running":
        return "draft"
    if status == "failed":
        return "failed"
    return "draft"


def _iteration_title(batch: DesignBatch) -> str:
    if batch.batch_name:
        return batch.batch_name.replace("IC", "Investment committee", 1) if batch.batch_name.startswith("IC") else batch.batch_name
    if batch.audience_label:
        return f"{batch.audience_label} iteration"
    if batch.scope_type == "selected_slides":
        return "Selected slide iteration"
    return "Whole deck iteration"


def _slide_thumbnail(slide: DeckSlide | None) -> str | None:
    if slide is None:
        return None
    if not (slide.rendered_image_path or slide.thumbnail_path):
        return None
    return f"/api/decks/{slide.deck_id}/slides/{slide.id}/preview"


def _status_label(status: str) -> str:
    labels = {
        "preparing": "In Progress",
        "ready_to_review": "Ready for Review",
        "failed": "Needs Attention",
        "exported": "Published",
        "reviewed": "Published",
    }
    return labels.get(status, status.replace("_", " ").title())


def _deck_company_name(deck: Deck) -> str | None:
    profile = getattr(deck, "brand_profile", None)
    if profile and profile.company_name:
        return profile.company_name
    return None


def _dashboard_user_name(user: User) -> str:
    if getattr(user, "name", None):
        return str(user.name).strip() or user.email.split("@", 1)[0]
    return user.email.split("@", 1)[0]


def _greeting(now: datetime, user: User) -> dict:
    hour = now.hour
    if hour < 12:
        salutation = "Good morning"
    elif hour < 18:
        salutation = "Good afternoon"
    else:
        salutation = "Good evening"
    return {
        "salutation": salutation,
        "userName": _dashboard_user_name(user),
        "subtitle": "Here's what's happening with your decks today.",
    }


def _serialize_deck(db: Session, deck: Deck) -> dict:
    sorted_slides = sorted(deck.slides, key=lambda slide: slide.slide_index)
    return {
        "id": deck.id,
        "title": deck.title,
        "description": deck.description or deck.summary or "",
        "audience": deck.audience or "",
        "purpose": deck.purpose or "",
        "status": _dashboard_deck_status(db, deck),
        "slideCount": deck.slide_count or len(sorted_slides),
        "thumbnailUrl": _slide_thumbnail(sorted_slides[0] if sorted_slides else None),
        "updatedAt": deck.updated_at.isoformat(),
    }


def _serialize_slide(slide: DeckSlide) -> dict:
    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "slideNumber": slide.slide_number or slide.slide_index,
        "title": slide.title,
        "thumbnailUrl": _slide_thumbnail(slide),
        "previewImageUrl": _slide_thumbnail(slide),
        "status": "original",
        "updatedAt": slide.updated_at.isoformat(),
    }


def _serialize_iteration(batch: DesignBatch) -> dict:
    sorted_slides = sorted(batch.deck.slides, key=lambda slide: slide.slide_index) if batch.deck is not None else []
    return {
        "id": batch.id,
        "deckId": batch.deck_id,
        "deckTitle": batch.deck.title if batch.deck is not None else "",
        "iterationNumber": batch.batch_number,
        "title": _iteration_title(batch),
        "scope": batch.scope_type,
        "status": _iteration_status(batch.status),
        "thumbnailUrl": _slide_thumbnail(sorted_slides[0] if sorted_slides else None),
        "updatedAt": (batch.updated_at or batch.created_at).isoformat(),
    }


def _serialize_recent_deck(deck: Deck, current_user: User, *, status: str) -> dict:
    initials = "".join(part[0] for part in _dashboard_user_name(current_user).split()[:2]).upper() or "U"
    sorted_slides = sorted(deck.slides, key=lambda slide: slide.slide_index)
    return {
        "id": deck.id,
        "title": deck.title,
        "companyName": _deck_company_name(deck),
        "thumbnailUrl": _slide_thumbnail(sorted_slides[0] if sorted_slides else None),
        "updatedAt": deck.updated_at.isoformat(),
        "status": status,
        "statusLabel": _status_label(status),
        "href": f"/decks/{deck.id}/smart-deck",
        "collaborators": [
            {
                "id": current_user.id,
                "name": _dashboard_user_name(current_user),
                "initials": initials,
                "avatarUrl": None,
                "isOwner": True,
            }
        ],
        "extraCollaboratorCount": 0,
    }


def _activity_item(kind: str, title: str, subtitle: str, created_at: datetime | None, *, deck_id: str | None = None, href: str | None = None, tone: str = "violet") -> dict:
    return {
        "id": f"{kind}:{deck_id or 'workspace'}:{created_at.isoformat() if created_at else 'unknown'}:{title}",
        "type": kind,
        "title": title,
        "subtitle": subtitle,
        "deckId": deck_id,
        "href": href,
        "createdAt": created_at.isoformat() if created_at else datetime.utcnow().isoformat(),
        "iconTone": tone,
    }


def _map_audit_activity(entry: AuditLog, deck_title_by_id: dict[str, str]) -> dict:
    action = str(entry.action or "activity")
    deck_title = deck_title_by_id.get(entry.deck_id, "Deck")
    href = f"/decks/{entry.deck_id}/smart-deck" if entry.deck_id else "/dashboard"
    if action == "deck.export":
        return _activity_item("deck_exported", "Deck exported", deck_title, entry.created_at, deck_id=entry.deck_id, href=href, tone="amber")
    if action == "workflow.due_diligence.queued":
        return _activity_item("llm_report_requested", "LLM report requested", deck_title, entry.created_at, deck_id=entry.deck_id, href=f"/decks/llm-report?deckId={entry.deck_id}", tone="violet")
    if action == "workflow.diligence_chat.message":
        return _activity_item("llm_report_updated", "LLM report updated", deck_title, entry.created_at, deck_id=entry.deck_id, href=f"/decks/llm-report?deckId={entry.deck_id}", tone="blue")
    if action == "deck.smart_edit.summary.generate":
        return _activity_item("slide_summary", "Slide summary generated", deck_title, entry.created_at, deck_id=entry.deck_id, href=href, tone="green")
    readable = action.split(".")[-1].replace("_", " ").title()
    return _activity_item("activity", readable, deck_title, entry.created_at, deck_id=entry.deck_id, href=href)


def _fallback_activity(decks: list[Deck], statuses: dict[str, str]) -> list[dict]:
    items: list[dict] = []
    for deck in decks[:5]:
        status = statuses[deck.id]
        items.append(
            _activity_item(
                "deck_status",
                f"{deck.title} is {_status_label(status).lower()}",
                _deck_company_name(deck) or deck.audience or "Deck workspace",
                deck.updated_at,
                deck_id=deck.id,
                href=f"/decks/{deck.id}/smart-deck",
                tone="violet" if status == "ready_to_review" else "blue",
            )
        )
    return items


def _build_recent_activity(db: Session, decks: list[Deck], statuses: dict[str, str]) -> list[dict]:
    deck_ids = [deck.id for deck in decks]
    if not deck_ids:
        return []
    audit_entries = (
        db.query(AuditLog)
        .filter(AuditLog.deck_id.in_(deck_ids))
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )
    deck_title_by_id = {deck.id: deck.title for deck in decks}
    activities = [_map_audit_activity(entry, deck_title_by_id) for entry in audit_entries[:5]]
    if activities:
        return activities
    return _fallback_activity(decks, statuses)


def _build_tasks(decks: list[Deck], statuses: dict[str, str]) -> list[dict]:
    tasks: list[dict] = []
    now = datetime.utcnow()
    for deck in decks:
        status = statuses[deck.id]
        if status == "ready_to_review":
            tasks.append(
                {
                    "id": f"task-review-{deck.id}",
                    "title": f"Review {deck.title}",
                    "deckId": deck.id,
                    "deckTitle": deck.title,
                    "priority": "high",
                    "status": "open",
                    "dueAt": now.isoformat(),
                    "href": f"/decks/{deck.id}/smart-deck",
                }
            )
        elif status == "preparing":
            tasks.append(
                {
                    "id": f"task-processing-{deck.id}",
                    "title": f"Check processing for {deck.title}",
                    "deckId": deck.id,
                    "deckTitle": deck.title,
                    "priority": "medium",
                    "status": "open",
                    "dueAt": (now + timedelta(days=1)).isoformat(),
                    "href": f"/decks/{deck.id}/processing",
                }
            )
        elif status == "failed":
            tasks.append(
                {
                    "id": f"task-failed-{deck.id}",
                    "title": f"Resolve {deck.title} processing issue",
                    "deckId": deck.id,
                    "deckTitle": deck.title,
                    "priority": "high",
                    "status": "open",
                    "dueAt": now.isoformat(),
                    "href": f"/decks/{deck.id}/processing",
                }
            )
    return tasks[:3]


def _notification_item(kind: str, title: str, body: str, href: str, created_at: datetime | None, *, deck_id: str | None = None) -> dict:
    return {
        "id": f"notification:{kind}:{deck_id or 'workspace'}:{created_at.isoformat() if created_at else 'unknown'}",
        "type": kind,
        "title": title,
        "body": body,
        "href": href,
        "deckId": deck_id,
        "createdAt": created_at.isoformat() if created_at else datetime.utcnow().isoformat(),
        "read": False,
    }


def _build_notifications(db: Session, decks: list[Deck]) -> dict:
    deck_ids = [deck.id for deck in decks]
    if not deck_ids:
        return {"unreadCount": 0, "items": []}

    title_by_deck = {deck.id: deck.title for deck in decks}
    diligence_artifacts = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id.in_(deck_ids),
            DeckLlmArtifact.artifact_type == AUDIENCE_DILIGENCE_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .limit(5)
        .all()
    )
    items = [
        _notification_item(
            "llm_report_ready",
            "LLM report ready",
            f"Your report for {title_by_deck.get(artifact.deck_id, 'this deck')} is available.",
            f"/decks/llm-report?deckId={artifact.deck_id}",
            artifact.created_at,
            deck_id=artifact.deck_id,
        )
        for artifact in diligence_artifacts
    ]
    return {"unreadCount": len(items), "items": items}


def _build_summary_cards(decks: list[Deck], statuses: dict[str, str], *, total_count: int) -> dict:
    total = total_count
    in_progress = sum(1 for status in statuses.values() if status == "preparing")
    ready = sum(1 for status in statuses.values() if status == "ready_to_review")
    published = sum(1 for deck in decks if str(deck.status or "").lower() in {"reviewed", "exported", "ready"})
    return {
        "totalDecks": total,
        "inProgressDecks": in_progress,
        "readyForReviewDecks": ready,
        "publishedDecks": published,
    }


def _scope_deck_query(db: Session, user: User):
    query = db.query(Deck)
    if user.role != "super_admin":
        query = query.join(Workspace, Workspace.id == Deck.workspace_id).filter(
            (Deck.user_id == user.id) | (Workspace.user_id == user.id)
        )
    return query


def get_workspace_dashboard(db: Session, user: User) -> dict:
    decks = (
        _scope_deck_query(db, user)
        .options(selectinload(Deck.file), selectinload(Deck.slides), selectinload(Deck.brand_profile))
        .order_by(Deck.updated_at.desc())
        .limit(8)
        .all()
    )
    statuses = {deck.id: _dashboard_deck_status(db, deck) for deck in decks}
    latest_deck = decks[0] if decks else None
    recent_slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == latest_deck.id)
        .order_by(DeckSlide.slide_index.asc())
        .limit(6)
        .all()
        if latest_deck is not None
        else []
    )
    latest_iterations_query = db.query(DesignBatch).join(Deck, Deck.id == DesignBatch.deck_id)
    if user.role != "super_admin":
        latest_iterations_query = latest_iterations_query.join(Workspace, Workspace.id == Deck.workspace_id).filter(
            (Deck.user_id == user.id) | (Workspace.user_id == user.id)
        )
    latest_iterations_query = latest_iterations_query.filter(DesignBatch.status != "archived")
    latest_iterations = latest_iterations_query.options(selectinload(DesignBatch.deck).selectinload(Deck.slides)).order_by(
        DesignBatch.updated_at.desc()
    ).limit(3).all()
    week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
    scoped_deck_ids = [deck.id for deck in decks]
    uploaded_count = _scope_deck_query(db, user).count()
    slides_count = db.query(DeckSlide).filter(DeckSlide.deck_id.in_(scoped_deck_ids)).count() if scoped_deck_ids else 0
    iterations_this_week = latest_iterations_query.filter(DesignBatch.created_at >= week_start).count()
    notifications = _build_notifications(db, decks)

    return {
        "greeting": _greeting(datetime.utcnow(), user),
        "summaryCards": _build_summary_cards(decks, statuses, total_count=uploaded_count),
        "user": {
            "id": user.id,
            "handle": user.email.split("@", 1)[0],
            "name": _dashboard_user_name(user),
            "role": user.role,
            "plan": "Pro plan",
        },
        "stats": {
            "uploadedDecks": uploaded_count,
            "iterationsThisWeek": iterations_this_week,
            "slidesInLibrary": slides_count,
            "teamMembers": 1 if user.role != "super_admin" else max(db.query(User).count(), 1),
        },
        "latestDeck": _serialize_deck(db, latest_deck) if latest_deck is not None else None,
        "decks": [_serialize_deck(db, deck) for deck in decks],
        "recentDecks": [_serialize_recent_deck(deck, user, status=statuses[deck.id]) for deck in decks[:5]],
        "recentSlides": [_serialize_slide(slide) for slide in recent_slides],
        "latestIterations": [_serialize_iteration(batch) for batch in latest_iterations],
        "recentActivity": _build_recent_activity(db, decks, statuses),
        "tasks": _build_tasks(decks, statuses),
        "notifications": notifications,
    }


def get_workspace_dashboard_notifications(db: Session, user: User) -> dict:
    dashboard = get_workspace_dashboard(db, user)
    return dashboard["notifications"]


def get_workspace_dashboard_tasks(db: Session, user: User) -> dict:
    dashboard = get_workspace_dashboard(db, user)
    return {"items": dashboard["tasks"]}
