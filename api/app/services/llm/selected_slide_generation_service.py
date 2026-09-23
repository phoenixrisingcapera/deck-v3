"""Selected-slide batching helpers.

This module preserves the useful part of the previous parallelization design:
split selected source slides into deterministic batches. Batch execution is
Python-first today, but the batch plan can be reused by a future execution
backend.

Audit note: `summarize_slide_generation_result` now calls the configured LLM
provider when credentials exist and requires normalized `source_fact_ids`. It
still returns workflow manifest data rather than persisted SmartDeckSuggestion
rows, so accept/reject should continue through the Smart Edit suggestion path.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.agents.llm_agent_utils import complete_json_with_ai_provider
from app.db.models import Deck, DeckSlide


SELECTED_SLIDE_GENERATION_SYSTEM_PROMPT = """You are a VC-style Smart Deck assistant.

Analyze the selected source slides and the user's instruction. Return JSON only.
Every recommendation must cite source_fact_ids from the provided facts. Do not
invent traction, market, customer, financial, team, or product claims that are
not present in the source facts.

Return this shape:
{
  "summary": "1-2 sentence VC-style analysis of the selected slides",
  "highlights": ["important deck-backed observations"],
  "recommendations": [
    {
      "slideId": "source slide id",
      "title": "short recommendation title",
      "recommendation": "specific improvement",
      "reason": "why this helps the investor-readiness of the slide",
      "source_fact_ids": ["fact_001"]
    }
  ],
  "risks": [
    {"risk": "missing or weak evidence", "source_fact_ids": ["fact_001"]}
  ],
  "source_fact_ids": ["all fact ids used"]
}
"""


def _word_count(value: str | None) -> int:
    if not value:
        return 0
    return len([token for token in value.split() if token.strip()])


def _selected_slides(db: Session, deck_id: str, selected_source_slide_ids: list[str]) -> list[DeckSlide]:
    """Load selected slides in caller-specified order and reject missing ids."""
    slides = (
        db.query(DeckSlide)
        .options(selectinload(DeckSlide.blocks))
        .filter(DeckSlide.deck_id == deck_id, DeckSlide.id.in_(selected_source_slide_ids))
        .all()
    )
    by_id = {slide.id: slide for slide in slides}
    ordered: list[DeckSlide] = []
    missing: list[str] = []
    for slide_id in selected_source_slide_ids:
        slide = by_id.get(slide_id)
        if slide is None:
            missing.append(slide_id)
            continue
        ordered.append(slide)
    if missing:
        raise ValueError(f"Selected source slides were not found on this deck: {', '.join(missing)}")
    return ordered


def build_selected_slide_batches(
    db: Session,
    *,
    deck: Deck,
    selected_source_slide_ids: list[str],
    prompt: str,
    partition_count: int,
    batch_size: int,
) -> dict[str, Any]:
    """Build deterministic batches; future execution backends can consume this plan."""
    selected_slides = _selected_slides(db, deck.id, selected_source_slide_ids)
    normalized_prompt = prompt.strip()
    normalized_batch_size = max(1, batch_size)
    batches: list[dict[str, Any]] = []

    for batch_index, start_index in enumerate(range(0, len(selected_slides), normalized_batch_size), start=1):
        chunk = selected_slides[start_index : start_index + normalized_batch_size]
        batches.append(
            {
                "taskId": f"{deck.id}:selected-slide-generation:{batch_index}",
                "batchIndex": batch_index,
                "slideIds": [slide.id for slide in chunk],
                "slides": [
                    {
                        "id": slide.id,
                        "slideNumber": int(slide.slide_number or int(slide.slide_index or 0) + 1),
                        "title": slide.title,
                        "rawText": slide.raw_text or "",
                        "blockCount": len(slide.blocks or []),
                        "wordCount": _word_count(slide.raw_text),
                    }
                    for slide in chunk
                ],
                "prompt": normalized_prompt,
                "deckId": deck.id,
                "partitionHint": partition_count,
            }
        )

    return {
        "deckId": deck.id,
        "deckTitle": deck.title,
        "prompt": normalized_prompt,
        "partitionCount": max(1, partition_count),
        "batchSize": normalized_batch_size,
        "selectedSourceSlideIds": selected_source_slide_ids,
        "selectedSlideCount": len(selected_slides),
        "batchCount": len(batches),
        "tasks": batches,
    }


def summarize_slide_generation_result(
    task: dict[str, Any],
    *,
    prompt: str,
    provider_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an evidence-bound analysis for one selected-slide batch.

    When a usable provider is configured, this calls the LLM with explicit source
    facts and normalizes the JSON response. If the provider is unavailable or
    returns invalid JSON, it falls back to a deterministic, fact-cited summary so
    the workflow still completes without hallucinated content.
    """
    slides = task.get("slides") if isinstance(task, dict) else []
    slides = slides if isinstance(slides, list) else []
    slide_titles = [str(slide.get("title") or f"Slide {slide.get('slideNumber') or index + 1}") for index, slide in enumerate(slides) if isinstance(slide, dict)]
    combined_text = " ".join(str(slide.get("rawText") or "") for slide in slides if isinstance(slide, dict)).strip()
    source_facts = _source_facts_for_task(slides)
    llm_payload = _call_selected_slide_llm(
        prompt=prompt,
        task=task,
        source_facts=source_facts,
        provider_config=provider_config,
    )
    if llm_payload is None:
        llm_payload = _fallback_generation_payload(prompt=prompt, slide_titles=slide_titles, combined_text=combined_text, source_facts=source_facts)
    normalized = _normalize_generation_payload(llm_payload, source_facts=source_facts)

    return {
        "taskId": task.get("taskId"),
        "batchIndex": task.get("batchIndex"),
        "slideIds": task.get("slideIds", []),
        "slideTitles": slide_titles,
        "slideCount": len(slides),
        "promptWordCount": len([word for word in prompt.split() if word.strip()]),
        "sourceWordCount": len([word for word in combined_text.split() if word.strip()]),
        "summary": normalized["summary"],
        "highlights": normalized["highlights"],
        "recommendations": normalized["recommendations"],
        "risks": normalized["risks"],
        "sourceFacts": source_facts,
        "sourceFactIds": normalized["source_fact_ids"],
        "status": "completed",
        "generationMode": "llm" if llm_payload.get("_mode") == "llm" else "deterministic",
    }


def _source_facts_for_task(slides: list[dict[str, Any]]) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    for slide_index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        raw_text = str(slide.get("rawText") or "").strip()
        if not raw_text:
            continue
        sentences = [item.strip() for item in raw_text.replace("\n", " ").split(".") if item.strip()]
        for sentence_index, sentence in enumerate(sentences[:4], start=1):
            facts.append(
                {
                    "fact_id": f"fact_{slide_index:02d}_{sentence_index:02d}",
                    "slide_id": str(slide.get("id") or ""),
                    "type": "deck_text",
                    "value": sentence[:500],
                }
            )
    return facts


def _call_selected_slide_llm(
    *,
    prompt: str,
    task: dict[str, Any],
    source_facts: list[dict[str, str]],
    provider_config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not provider_config or provider_config.get("provider") in {"deterministic", "fallback", "missing", "missing_provider"}:
        return None
    if not provider_config.get("apiKey"):
        return None

    user_prompt = {
        "instruction": prompt,
        "taskId": task.get("taskId"),
        "slides": task.get("slides") or [],
        "source_facts": source_facts,
    }
    result = complete_json_with_ai_provider(
        provider_config=provider_config,
        system=SELECTED_SLIDE_GENERATION_SYSTEM_PROMPT,
        user=f"Analyze this selected-slide batch and return JSON only:\n{user_prompt}",
        max_tokens=3000,
    )
    if isinstance(result, dict):
        result["_mode"] = "llm"
        return result
    return None


def _fallback_generation_payload(
    *,
    prompt: str,
    slide_titles: list[str],
    combined_text: str,
    source_facts: list[dict[str, str]],
) -> dict[str, Any]:
    combined_words = [word for word in combined_text.split() if word.strip()]
    summary_snippet = " ".join(combined_words[:40]) if combined_words else "No slide text available."
    if len(summary_snippet) > 220:
        summary_snippet = f"{summary_snippet[:217].rstrip()}..."
    fact_ids = [fact["fact_id"] for fact in source_facts[:5]]
    return {
        "_mode": "deterministic",
        "summary": f"{prompt.strip()} :: {summary_snippet}",
        "highlights": slide_titles[:5],
        "recommendations": [
            {
                "slideId": source_facts[0]["slide_id"] if source_facts else "",
                "title": "Add evidence-backed investor takeaway",
                "recommendation": "Clarify the investor takeaway using only the cited deck facts.",
                "reason": "The selected text can be made more decision-ready without adding unsupported claims.",
                "source_fact_ids": fact_ids,
            }
        ] if source_facts else [],
        "risks": [
            {
                "risk": "Limited extracted source facts; avoid adding new claims until evidence is available.",
                "source_fact_ids": fact_ids,
            }
        ],
        "source_fact_ids": fact_ids,
    }


def _normalize_generation_payload(payload: dict[str, Any], *, source_facts: list[dict[str, str]]) -> dict[str, Any]:
    allowed_fact_ids = {fact["fact_id"] for fact in source_facts}
    source_fact_ids = [str(item) for item in payload.get("source_fact_ids", []) if str(item) in allowed_fact_ids] if isinstance(payload.get("source_fact_ids"), list) else []

    recommendations = []
    for item in payload.get("recommendations", []) if isinstance(payload.get("recommendations"), list) else []:
        if not isinstance(item, dict):
            continue
        item_fact_ids = [str(fid) for fid in item.get("source_fact_ids", []) if str(fid) in allowed_fact_ids] if isinstance(item.get("source_fact_ids"), list) else []
        source_fact_ids.extend(fid for fid in item_fact_ids if fid not in source_fact_ids)
        recommendations.append(
            {
                "slideId": str(item.get("slideId") or item.get("slide_id") or ""),
                "title": str(item.get("title") or "Smart Deck recommendation")[:180],
                "recommendation": str(item.get("recommendation") or item.get("suggested_text") or "")[:2000],
                "reason": str(item.get("reason") or "Improves investor-readiness using cited source facts.")[:1200],
                "source_fact_ids": item_fact_ids,
            }
        )

    risks = []
    for item in payload.get("risks", []) if isinstance(payload.get("risks"), list) else []:
        if isinstance(item, dict):
            item_fact_ids = [str(fid) for fid in item.get("source_fact_ids", []) if str(fid) in allowed_fact_ids] if isinstance(item.get("source_fact_ids"), list) else []
            risks.append({"risk": str(item.get("risk") or "Evidence risk")[:1000], "source_fact_ids": item_fact_ids})
        elif isinstance(item, str):
            risks.append({"risk": item[:1000], "source_fact_ids": []})

    if allowed_fact_ids and not source_fact_ids:
        source_fact_ids = list(sorted(allowed_fact_ids))[:3]

    return {
        "summary": str(payload.get("summary") or "Selected slides analyzed with available deck evidence."),
        "highlights": [str(item)[:300] for item in payload.get("highlights", [])[:5]] if isinstance(payload.get("highlights"), list) else [],
        "recommendations": recommendations,
        "risks": risks,
        "source_fact_ids": source_fact_ids,
    }


def summarize_slide_generation_manifest(tasks: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize batch execution for workflow artifacts and admin visibility."""
    slide_ids = [slide_id for task in tasks for slide_id in (task.get("slideIds") or [])]
    completed_results = [result for result in results if isinstance(result, dict) and result.get("status") == "completed"]
    failed_results = [result for result in results if isinstance(result, dict) and result.get("status") == "failed"]
    return {
        "taskCount": len(tasks),
        "resultCount": len(results),
        "selectedSourceSlideIds": slide_ids,
        "completedTaskIds": [result.get("taskId") for result in completed_results],
        "failedTaskIds": [result.get("taskId") for result in failed_results],
        "failedTaskCount": len(failed_results),
        "slideCount": sum(int(result.get("slideCount") or 0) for result in completed_results),
    }
