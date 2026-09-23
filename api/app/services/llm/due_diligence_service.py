from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.llm.deck_chunking_service import sync_deck_vector_chunks
from app.services.llm.generation_service import _fit_text, _load_deck, get_generation_provider_config
from app.services.llm import default_registry
from app.services.llm.prompt_package_loader import build_prompt_package_text, load_prompt_package
from app.services.llm.response_models import LlmGenerationConfig
from app.services.llm.structured_json_service import call_structured_json
from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks
from app.services.llm.vision_context_service import build_visual_context, prompt_safe_visual_context
from app.services.brand.brand_design_tokens import build_brand_llm_context


DUE_DILIGENCE_CLAIMS_ARTIFACT_TYPE = "due_diligence_claims"
DUE_DILIGENCE_RISKS_ARTIFACT_TYPE = "due_diligence_risks"
DUE_DILIGENCE_REPORT_ARTIFACT_TYPE = "due_diligence_report"
DUE_DILIGENCE_CHAT_ARTIFACT_TYPE = "due_diligence_chat"
_DILIGENCE_CHAT_HISTORY_LIMIT = 40
_DILIGENCE_CHAT_RESERVATION_SCHEMA = "due-diligence-chat-exchange.v1"
_DILIGENCE_CHAT_WAIT_SECONDS = 10.0
_DILIGENCE_CHAT_POLL_SECONDS = 0.05


@dataclass(frozen=True)
class DiligenceExchangePending:
    client_exchange_key: str


class DiligenceExchangeOwnershipLost(RuntimeError):
    """Raised when a late completion no longer owns its reservation."""


def _conversation_query(db: Session, deck_id: str, *, user_id: str, audience: str):
    return db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck_id,
        DeckLlmArtifact.artifact_type == DUE_DILIGENCE_CHAT_ARTIFACT_TYPE,
        DeckLlmArtifact.artifact_key == f"{user_id}:{audience}",
    )


def _conversation_payload(artifact: DeckLlmArtifact | None, deck_id: str, *, user_id: str, audience: str) -> dict | None:
    if artifact is None or artifact.status != "ready":
        return None
    payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
    if payload.get("deckId") != deck_id or payload.get("userId") != user_id or payload.get("audience") != audience:
        raise ValueError("Diligence conversation ownership does not match this request.")
    return {**payload, "messages": list(payload.get("messages") or [])[-_DILIGENCE_CHAT_HISTORY_LIMIT:]}


def get_diligence_conversation(db: Session, deck_id: str, *, user_id: str, audience: str) -> dict | None:
    return _conversation_payload(_conversation_query(db, deck_id, user_id=user_id, audience=audience).one_or_none(), deck_id, user_id=user_id, audience=audience)


def _exchange_query(db: Session, deck_id: str, *, user_id: str, audience: str, client_exchange_key: str):
    return db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck_id,
        DeckLlmArtifact.artifact_type == DUE_DILIGENCE_CHAT_ARTIFACT_TYPE,
        DeckLlmArtifact.identity_user_id == user_id,
        DeckLlmArtifact.identity_audience == audience,
        DeckLlmArtifact.client_exchange_key == client_exchange_key,
    )


def _completed_exchange(artifact: DeckLlmArtifact) -> dict | None:
    payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
    if artifact.status != "ready" or not payload.get("reply"):
        return None
    return {
        "conversationId": payload["conversationId"],
        "messageId": payload["messageId"],
        "reply": payload["reply"],
        "provider": payload.get("provider"),
        "model": payload.get("model"),
    }


def reserve_diligence_exchange(
    db: Session,
    deck_id: str,
    *,
    user_id: str,
    audience: str,
    conversation_id: str | None,
    client_exchange_key: str,
    user_content: str,
) -> tuple[DeckLlmArtifact | dict | DiligenceExchangePending, bool]:
    """Commit one owner before provider work; duplicates only wait or replay."""
    query = _exchange_query(db, deck_id, user_id=user_id, audience=audience, client_exchange_key=client_exchange_key)
    now = datetime.utcnow()
    artifact = query.with_for_update().one_or_none()
    if artifact is not None:
        completed = _completed_exchange(artifact)
        if completed:
            db.commit()
            return completed, True
        db.commit()
        deadline = time.monotonic() + _DILIGENCE_CHAT_WAIT_SECONDS
        while time.monotonic() < deadline:
            db.expire_all()
            current = query.one_or_none()
            if current is not None:
                completed = _completed_exchange(current)
                if completed:
                    return completed, True
            time.sleep(_DILIGENCE_CHAT_POLL_SECONDS)
        return DiligenceExchangePending(client_exchange_key=client_exchange_key), True

    ownership_token = generate_id("ddowner")
    artifact = DeckLlmArtifact(
        id=generate_id("artifact"),
        deck_id=deck_id,
        artifact_type=DUE_DILIGENCE_CHAT_ARTIFACT_TYPE,
        artifact_key=f"exchange:{client_exchange_key}",
        identity_user_id=user_id,
        identity_audience=audience,
        client_exchange_key=client_exchange_key,
        schema_version=_DILIGENCE_CHAT_RESERVATION_SCHEMA,
        status="pending",
        summary="Due Diligence chat exchange reservation.",
        payload_json={
            "conversationId": conversation_id,
            "userContent": user_content,
            "reservedAt": now.replace(tzinfo=timezone.utc).isoformat(),
            "ownershipToken": ownership_token,
        },
    )
    db.add(artifact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return reserve_diligence_exchange(
            db,
            deck_id,
            user_id=user_id,
            audience=audience,
            conversation_id=conversation_id,
            client_exchange_key=client_exchange_key,
            user_content=user_content,
        )
    return artifact, False


def complete_diligence_exchange(
    db: Session,
    reservation_id: str,
    *,
    ownership_token: str,
    conversation_id: str,
    message_id: str,
    reply: str,
    provider: str | None,
    model: str | None,
) -> None:
    completed_payload = {
        "conversationId": conversation_id,
        "messageId": message_id,
        "reply": reply,
        "provider": provider,
        "model": model,
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    updated = db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.id == reservation_id,
        DeckLlmArtifact.status == "pending",
        DeckLlmArtifact.payload_json["ownershipToken"].as_string() == ownership_token,
    ).update(
        {
            DeckLlmArtifact.status: "ready",
            DeckLlmArtifact.payload_json: completed_payload,
            DeckLlmArtifact.metrics_json: {"provider": provider, "model": model},
            DeckLlmArtifact.updated_at: datetime.utcnow(),
        },
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        raise DiligenceExchangeOwnershipLost("Diligence exchange completion no longer owns its reservation.")
    db.commit()


def persist_diligence_exchange(
    db: Session,
    deck_id: str,
    *,
    user_id: str,
    audience: str,
    conversation_id: str | None,
    client_exchange_key: str,
    user_content: str,
    assistant_content: str,
    provider: str | None = None,
    model: str | None = None,
) -> tuple[dict, bool]:
    query = _conversation_query(db, deck_id, user_id=user_id, audience=audience)
    artifact = query.with_for_update().one_or_none()
    conversation = _conversation_payload(artifact, deck_id, user_id=user_id, audience=audience)
    if conversation is not None and conversation_id and conversation.get("conversationId") != conversation_id:
        raise ValueError("Diligence conversation does not match this deck, user, and audience.")
    if conversation is None:
        if conversation_id:
            raise ValueError("Diligence conversation does not match this deck, user, and audience.")
        conversation = {
            "conversationId": generate_id("ddchat"),
            "deckId": deck_id,
            "userId": user_id,
            "audience": audience,
            "messages": [],
        }
    messages = list(conversation.get("messages") or [])
    replay = next((item for item in messages if item.get("clientExchangeKey") == client_exchange_key and item.get("role") == "assistant"), None)
    if replay:
        return {**conversation, "messages": messages[-_DILIGENCE_CHAT_HISTORY_LIMIT:], "messageId": replay["messageId"], "reply": replay["content"]}, True
    now = datetime.now(timezone.utc).isoformat()
    messages.extend([
        {"messageId": generate_id("ddmsg"), "role": "user", "content": user_content, "clientExchangeKey": client_exchange_key, "createdAt": now},
        {"messageId": generate_id("ddmsg"), "role": "assistant", "content": assistant_content, "clientExchangeKey": client_exchange_key, "createdAt": now, "provider": provider, "model": model},
    ])
    conversation["messages"] = messages[-_DILIGENCE_CHAT_HISTORY_LIMIT:]
    if artifact is None:
        artifact = DeckLlmArtifact(
            id=generate_id("artifact"), deck_id=deck_id, artifact_type=DUE_DILIGENCE_CHAT_ARTIFACT_TYPE,
            artifact_key=f"{user_id}:{audience}", schema_version="due-diligence-chat.v1", status="ready",
        )
        db.add(artifact)
    artifact.summary = "Durable Due Diligence conversation."
    artifact.payload_json = conversation
    artifact.metrics_json = {"messageCount": len(conversation["messages"]), "updatedAt": now}
    try:
        db.commit()
    except IntegrityError:
        # PostgreSQL's unique artifact identity resolves simultaneous first
        # writers atomically. Reload and replay the winner after rollback.
        db.rollback()
        artifact = query.with_for_update().one_or_none()
        conversation = _conversation_payload(artifact, deck_id, user_id=user_id, audience=audience)
        replay = next((item for item in (conversation or {}).get("messages", []) if item.get("clientExchangeKey") == client_exchange_key and item.get("role") == "assistant"), None)
        if replay:
            return {**conversation, "messageId": replay["messageId"], "reply": replay["content"], "provider": replay.get("provider"), "model": replay.get("model")}, True
        raise
    assistant = conversation["messages"][-1]
    return {**conversation, "messageId": assistant["messageId"], "reply": assistant["content"]}, False


def extract_due_diligence_claims(db: Session, deck_id: str) -> dict:
    return _run_due_diligence_step(db, deck_id=deck_id, artifact_type=DUE_DILIGENCE_CLAIMS_ARTIFACT_TYPE, section="claim_extractor")


def analyze_due_diligence_risks(db: Session, deck_id: str) -> dict:
    return _run_due_diligence_step(db, deck_id=deck_id, artifact_type=DUE_DILIGENCE_RISKS_ARTIFACT_TYPE, section="risk_analyzer")


def build_due_diligence_report(db: Session, deck_id: str) -> dict:
    return _run_due_diligence_step(db, deck_id=deck_id, artifact_type=DUE_DILIGENCE_REPORT_ARTIFACT_TYPE, section="ic_memo")


def get_latest_due_diligence_report(db: Session, deck_id: str) -> dict | None:
    artifact = _find_latest_artifact(db, deck_id, DUE_DILIGENCE_REPORT_ARTIFACT_TYPE)
    if artifact is None:
        return None
    return {
        "runId": artifact.artifact_key,
        "deckId": deck_id,
        "status": "completed",
        "report": artifact.payload_json,
        "cached": True,
    }


def _run_due_diligence_step(db: Session, *, deck_id: str, artifact_type: str, section: str) -> dict:
    cached = _find_latest_artifact(db, deck_id, artifact_type)
    if cached and cached.payload_json:
        return {
            "runId": cached.artifact_key,
            "deckId": deck_id,
            "status": "completed",
            "report": cached.payload_json,
            "cached": True,
        }

    deck = _load_deck(db, deck_id)
    if deck is None:
        return {"runId": "", "deckId": deck_id, "status": "failed", "report": None, "cached": False}

    chunk_sync = sync_deck_vector_chunks(db, deck_id, audience_label=deck.audience)
    retrieval = retrieve_relevant_chunks(
        db,
        deck_id=deck_id,
        query_text="Material claims unsupported claims diligence risks investor questions and IC memo context",
        chunk_types=["deck_summary", "slide_raw_text", "slide_block", "brand_profile", "market_research", "deck_map_analysis", "accepted_edit", "diligence_lens", "audience_profile"],
        limit=12,
    )
    visual_context = build_visual_context(deck, limit=4)
    context = {
        "schemaVersion": "due-diligence-workflow.v1",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
        },
        "slides": [
            {
                "id": slide.id,
                "title": slide.title,
                "role": slide.role,
                "rawText": slide.raw_text,
            }
            for slide in sorted(deck.slides, key=lambda item: item.slide_index)
        ],
        "brand": build_brand_llm_context(deck.brand_profile),
        "vectorRetrieval": retrieval,
        "vectorSync": chunk_sync,
        "visualContext": prompt_safe_visual_context(visual_context),
        "promptPackage": {
            "name": "due_diligence",
            "version": load_prompt_package("due_diligence")["version"],
            "section": section,
        },
    }
    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="analysis")
    raw = call_structured_json(
        provider=config["provider"],
        model=config["model"],
        api_key=config.get("apiKey"),
        system_prompt="You output only valid JSON for backend-validated due diligence workflow output.",
        user_prompt=build_prompt_package_text("due_diligence", section, context_label="Due diligence context", context=context),
        timeout=90,
        max_tokens=4000,
        image_urls=visual_context.get("imageUrls"),
        credential_source=config.get("source", "environment"),
    )
    validated = _validate_due_diligence_report(raw, deck_id=deck_id, context=context, provider=config["provider"], model=config["model"])
    run_id = generate_id("dd")
    _record_due_diligence_artifact(db, deck_id=deck_id, artifact_type=artifact_type, artifact_key=run_id, payload_json=validated)
    db.commit()
    return {"runId": run_id, "deckId": deck_id, "status": "completed", "report": validated, "cached": False}


def _validate_due_diligence_report(raw: dict, *, deck_id: str, context: dict, provider: str, model: str | None) -> dict:
    claims_raw = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    risks_raw = raw.get("risks") if isinstance(raw.get("risks"), list) else []
    unsupported_claims = [str(item)[:500] for item in raw.get("unsupportedClaims", []) if str(item).strip()][:20]
    investor_questions = [str(item)[:500] for item in raw.get("investorQuestions", []) if str(item).strip()][:20]
    client_request_list = [str(item)[:500] for item in raw.get("clientRequestList", []) if str(item).strip()][:20]

    claims = []
    for item in claims_raw[:30]:
        if not isinstance(item, dict):
            continue
        claim_text = _fit_text(str(item.get("claim") or item.get("claimText") or ""), 600)
        if not claim_text:
            continue
        claims.append(
            {
                "claim": claim_text,
                "slideId": str(item.get("slideId") or "") or None,
                "slideTitle": _fit_text(str(item.get("slideTitle") or ""), 200) or None,
                "evidenceStatus": str(item.get("evidenceStatus") or "unsupported")[:40],
                "riskLevel": str(item.get("riskLevel") or "medium")[:40],
                "confidence": str(item.get("confidence") or "medium")[:40],
                "sourceFactIds": [str(fact)[:80] for fact in item.get("sourceFactIds", []) if str(fact).strip()][:20],
            }
        )

    risks = []
    for item in risks_raw[:20]:
        if not isinstance(item, dict):
            continue
        risk_text = _fit_text(str(item.get("risk") or ""), 400)
        if not risk_text:
            continue
        risks.append(
            {
                "risk": risk_text,
                "category": _fit_text(str(item.get("category") or "general"), 80),
                "severity": _fit_text(str(item.get("severity") or "medium"), 40),
                "evidenceStatus": _fit_text(str(item.get("evidenceStatus") or "unknown"), 40),
                "investorQuestion": _fit_text(str(item.get("investorQuestion") or "What evidence supports this claim?"), 500),
                "mitigation": _fit_text(str(item.get("mitigation") or ""), 500) or None,
            }
        )

    return {
        "deckId": deck_id,
        "claims": claims,
        "unsupportedClaims": unsupported_claims,
        "evidenceStatusSummary": raw.get("evidenceStatusSummary") if isinstance(raw.get("evidenceStatusSummary"), dict) else {},
        "risks": risks,
        "investorQuestions": investor_questions,
        "icMemoSummary": _fit_text(str(raw.get("icMemoSummary") or (raw.get("icMemo") or {}).get("summary") or ""), 1200),
        "clientRequestList": client_request_list,
        "system": {
            "provider": provider,
            "model": model,
            "promptPackage": context["promptPackage"],
            "vectorRetrieval": {
                "status": (context.get("vectorRetrieval") or {}).get("status"),
                "message": (context.get("vectorRetrieval") or {}).get("message"),
                "chunkCount": len((context.get("vectorRetrieval") or {}).get("chunks") or []),
            },
            "vectorSync": {
                "status": (context.get("vectorSync") or {}).get("status"),
                "message": (context.get("vectorSync") or {}).get("message"),
                "chunkCount": (context.get("vectorSync") or {}).get("chunkCount"),
            },
        },
    }


def _find_latest_artifact(db: Session, deck_id: str, artifact_type: str) -> DeckLlmArtifact | None:
    return (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == artifact_type,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )


def _record_due_diligence_artifact(db: Session, *, deck_id: str, artifact_type: str, artifact_key: str, payload_json: dict) -> None:
    db.add(
        DeckLlmArtifact(
            id=generate_id("artifact"),
            deck_id=deck_id,
            artifact_type=artifact_type,
            artifact_key=artifact_key,
            schema_version="due-diligence-workflow.v1",
            status="ready",
            summary=_fit_text(str(payload_json.get("icMemoSummary") or "Due diligence report generated."), 500),
            payload_json=payload_json,
            metrics_json={"generatedAt": datetime.now(timezone.utc).isoformat()},
        )
    )


# ---------------------------------------------------------------------------
# Due Diligence Chat
# ---------------------------------------------------------------------------

_DILIGENCE_CHAT_SYSTEM_PROMPT = """\
You are a due diligence analyst assistant for a pitch deck review platform. \
You help investors and analysts interrogate, validate, and understand claims, \
risks, audience fit, and IC memo findings for a specific deck.

You have access to the deck's diligence workspace including claims, risk register, \
audience fit analysis, IC memo summary, domain scores, and LP view. \
Use this workspace context when answering questions.

Rules:
- Be specific and reference actual workspace data when possible.
- If a question is about a claim, reference the claim text and its evidence status.
- If a question is about a risk, reference the risk category, severity, and mitigation.
- If a question is about audience fit, reference the fit score and specific strengths/weaknesses.
- If a question is about the IC memo, reference the thesis, reasons to believe, and main risks.
- Be concise. Default to 2-4 sentences unless the user asks for depth.
- Do not fabricate data that is not in the workspace context.
- If the workspace has no data for a specific topic, say so clearly.\
"""


def chat_with_diligence_workspace(
    db: Session,
    deck_id: str,
    *,
    messages: list[dict],
    audience: str | None = None,
) -> dict:
    """Send a chat message in the context of the deck's diligence workspace.

    Returns ``{"reply": str, "provider": str, "model": str}``.
    """
    deck = _load_deck(db, deck_id)
    if deck is None:
        raise ValueError("Deck not found")

    # Build lightweight workspace context from persisted artifacts.
    workspace_context = _build_chat_workspace_context(db, deck_id, audience=audience or deck.audience)

    system_prompt = _DILIGENCE_CHAT_SYSTEM_PROMPT + "\n\n--- Diligence Workspace Context ---\n" + workspace_context

    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="analysis")

    provider = config.get("provider", "openai")
    model = config.get("model")
    api_key = config.get("apiKey")

    if not model or not api_key:
        raise ValueError("AI provider credentials are not configured for this workspace.")

    # NEW: Dispatch through the canonical provider registry instead of provider-
    # specific signatures. Difference: every configured provider receives the
    # same bounded conversation transcript, not only the final user message.
    conversation = "\n\n".join(
        f"{str(msg.get('role') or 'user').upper()}: {str(msg.get('content') or '')}"
        for msg in messages[-20:]
    )
    response = default_registry.get(provider).generate_text(
        system=system_prompt,
        user=conversation,
        config=LlmGenerationConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            max_tokens=2000,
            timeout_seconds=60,
        ),
    )
    reply = response.content or ""

    return {
        "reply": _fit_text(reply.strip(), 8000) or "I was unable to generate a response. Please try again.",
        "provider": response.provider or provider,
        "model": response.model or model,
    }


def _build_chat_workspace_context(db: Session, deck_id: str, *, audience: str | None) -> str:
    """Build a concise text summary of the diligence workspace for LLM context."""
    from app.services.visualizer.generated_deck_read_model import build_due_diligence_workspace_payload

    payload = build_due_diligence_workspace_payload(db, deck_id, audience=audience)
    if payload is None:
        return "No diligence workspace data available for this deck."

    parts: list[str] = []

    deck = payload.get("deck") or {}
    parts.append(f"Deck: {deck.get('title', 'Unknown')} (audience: {audience or 'not specified'})")

    summary = payload.get("summary") or {}
    if summary:
        score = summary.get("investment_readiness_score", "N/A")
        parts.append(f"Investment readiness score: {score}")
        if summary.get("evidence_quality"):
            parts.append(f"Evidence quality: {summary['evidence_quality']}")
        if summary.get("market_claim_risk"):
            parts.append(f"Market claim risk: {summary['market_claim_risk']}")

    claims = payload.get("claims") or []
    if claims:
        parts.append(f"\nClaims ({len(claims)} total):")
        for claim in claims[:10]:
            parts.append(
                f"- [{claim.get('evidenceStatus', '?')}] "
                f"(risk: {claim.get('riskLevel', '?')}, confidence: {claim.get('confidence', '?')}) "
                f"{claim.get('claimText', claim.get('claim', ''))[:200]}"
            )

    risks = payload.get("riskRegister") or payload.get("risks") or []
    if risks:
        parts.append(f"\nRisk Register ({len(risks)} total):")
        for risk in risks[:8]:
            parts.append(
                f"- [{risk.get('severity', '?')}] {risk.get('category', '')}: "
                f"{risk.get('risk', '')[:200]}"
                + (f" | Mitigation: {risk.get('mitigation', '')[:120]}" if risk.get("mitigation") else "")
            )

    audience_fit = payload.get("audienceFit") or {}
    if audience_fit:
        parts.append(f"\nAudience Fit (score: {audience_fit.get('fitScore', 'N/A')}):")
        for s in (audience_fit.get("strengths") or [])[:5]:
            parts.append(f"  + Strength: {s[:150]}")
        for w in (audience_fit.get("weaknesses") or [])[:5]:
            parts.append(f"  - Weakness: {w[:150]}")

    ic_memo = payload.get("icMemo") or {}
    if ic_memo:
        parts.append(f"\nIC Memo: {ic_memo.get('thesis', '')[:300]}")
        if ic_memo.get("recommendation"):
            parts.append(f"Recommendation: {ic_memo['recommendation'][:200]}")

    return "\n".join(parts) if parts else "No diligence workspace data available."
