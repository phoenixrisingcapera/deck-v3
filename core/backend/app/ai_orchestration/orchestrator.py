from __future__ import annotations

from datetime import datetime
from time import perf_counter

from sqlalchemy.orm import Session, selectinload

from app.ai_orchestration.context_builder import SmartDeckContextBuilder
from app.ai_orchestration.errors import AiOrchestrationError, SceneGraphValidationError
from app.ai_orchestration.providers import BaseLlmProvider
from app.ai_orchestration.schemas import AiOrchestrationRequest, AiOrchestrationResponse, AiRunResponse
from app.ai_orchestration.validators import SceneGraphValidator
from app.core.security import generate_id
from app.db.models import (
    AiRun,
    AiRunStep,
    Deck,
    DeckLlmArtifact,
    DeckSlide,
    DesignBatch,
    DesignBatchSlide,
    GeneratedSlideCandidate,
    User,
)
from app.observability import start_span
from app.services.rendering.final_deck_service import GENERATED_SLIDE_ARTIFACT_TYPE
from app.services.admin.agent_telemetry import record_agent_event, record_run_failed, record_run_started
from app.services.platform.shell.shell_service import get_design_batch


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def serialize_ai_run(ai_run: AiRun) -> dict:
    return {
        "id": ai_run.id,
        "deckId": ai_run.deck_id,
        "workspaceId": ai_run.workspace_id,
        "status": ai_run.status,
        "mode": ai_run.mode,
        "selectedSlideIds": ai_run.selected_slide_ids_json or [],
        "provider": ai_run.provider,
        "model": ai_run.model,
        "createdAt": _iso(ai_run.created_at),
        "completedAt": _iso(ai_run.completed_at),
    }


class SmartDeckOrchestrator:
    def __init__(
        self,
        *,
        context_builder: SmartDeckContextBuilder | None = None,
        provider: BaseLlmProvider | None = None,
        validator: SceneGraphValidator | None = None,
    ) -> None:
        self.context_builder = context_builder or SmartDeckContextBuilder()
        if provider is None:
            raise ValueError("SmartDeckOrchestrator requires an explicit AI provider.")
        self.provider = provider
        self.validator = validator or SceneGraphValidator()

    def run(self, db: Session, *, user: User, request: AiOrchestrationRequest) -> AiOrchestrationResponse:
        with start_span(
            "deck_aistack.orchestrate",
            attributes={"deck_id": request.deck_id, "mode": request.mode, "selected_slide_count": len(request.selected_slide_ids)},
        ):
            return self._run_with_span(db, user=user, request=request)

    def _run_with_span(self, db: Session, *, user: User, request: AiOrchestrationRequest) -> AiOrchestrationResponse:
        deck = db.query(Deck).filter(Deck.id == request.deck_id).one_or_none()
        if deck is None:
            raise AiOrchestrationError("Deck not found")

        now = datetime.utcnow()
        ai_run = AiRun(
            id=generate_id("airun"),
            workspace_id=deck.workspace_id,
            deck_id=deck.id,
            user_id=user.id,
            intent="smart_deck_generation",
            mode=request.mode,
            user_instruction=request.user_instruction.strip(),
            selected_slide_ids_json=request.selected_slide_ids,
            audience=request.audience or deck.audience,
            provider=self.provider.name,
            model=request.preferred_model or self.provider.model,
            status="running",
            created_at=now,
            updated_at=now,
        )
        db.add(ai_run)
        db.flush()
        record_run_started(
            db,
            run_id=ai_run.id,
            run_type="deck_aistack_orchestration",
            workspace_id=ai_run.workspace_id,
            deck_id=ai_run.deck_id,
            user_id=ai_run.user_id,
            provider=ai_run.provider,
            model=ai_run.model,
            metadata={"mode": ai_run.mode, "selectedSlideCount": len(ai_run.selected_slide_ids_json or [])},
        )

        try:
            context = self._step(db, ai_run, "build_context", {}, lambda: self.context_builder.build(
                db,
                deck_id=deck.id,
                selected_slide_ids=request.selected_slide_ids,
                user_instruction=request.user_instruction,
                audience=request.audience,
            ))
            output = self._step(db, ai_run, "generate_scene_graph", {"provider": self.provider.name}, lambda: self.provider.generate_slide_versions(context))
            validation = self.validator.validate_output(output, request.selected_slide_ids)
            self._step(
                db,
                ai_run,
                "validate_scene_graph",
                {"selectedSlideIds": request.selected_slide_ids},
                lambda: {"valid": validation.valid, "messages": validation.messages},
            )
            if not validation.valid:
                raise SceneGraphValidationError("; ".join(validation.messages))

            batch = self._step(
                db,
                ai_run,
                "save_generation_batch",
                {"slideCount": len(output.generated_slides)},
                lambda: self._save_batch(db, deck, request, output, ai_run.id),
            )
            ai_run.status = "completed"
            ai_run.completed_at = datetime.utcnow()
            ai_run.updated_at = ai_run.completed_at
            ai_run.result_json = {"batchId": batch.id, "generatedSlideVersionCount": len(output.generated_slides)}
            db.add(ai_run)
            record_agent_event(
                db,
                event_name="ai.run.completed",
                run_type="deck_aistack_orchestration",
                workspace_id=ai_run.workspace_id,
                deck_id=ai_run.deck_id,
                user_id=ai_run.user_id,
                run_id=ai_run.id,
                status="completed",
                provider=ai_run.provider,
                model=ai_run.model,
                metadata={"batchId": batch.id, "generatedSlideVersionCount": len(output.generated_slides)},
            )
            db.commit()

            batch_detail = get_design_batch(db, deck.id, batch.id)
            if batch_detail is None:
                raise AiOrchestrationError("Generated batch could not be reloaded")
            db.refresh(ai_run)
            return AiOrchestrationResponse(
                runId=ai_run.id,
                deckId=deck.id,
                status=ai_run.status,
                batchId=batch.id,
                batch=batch_detail,
                generatedSlideVersions=batch_detail.get("candidateSlides", []),
                aiRun=AiRunResponse(**serialize_ai_run(ai_run)),
            )
        except Exception as exc:
            ai_run.status = "failed"
            ai_run.error_message = str(exc)
            ai_run.completed_at = datetime.utcnow()
            ai_run.updated_at = ai_run.completed_at
            db.add(ai_run)
            record_run_failed(
                db,
                run_id=ai_run.id,
                run_type="deck_aistack_orchestration",
                workspace_id=ai_run.workspace_id,
                deck_id=ai_run.deck_id,
                user_id=ai_run.user_id,
                provider=ai_run.provider,
                model=ai_run.model,
                error_category=_error_category_for_exception(exc),
                error_message=str(exc),
                metadata={"mode": ai_run.mode, "selectedSlideCount": len(ai_run.selected_slide_ids_json or [])},
            )
            db.commit()
            raise

    def _step(self, db: Session, ai_run: AiRun, step_name: str, input_json: dict, func):
        with start_span(
            f"deck_aistack.{step_name}",
            attributes={"ai_run_id": ai_run.id, "deck_id": ai_run.deck_id, "step_name": step_name},
        ):
            return self._step_with_span(db, ai_run, step_name, input_json, func)

    def _step_with_span(self, db: Session, ai_run: AiRun, step_name: str, input_json: dict, func):
        started_at = perf_counter()
        step = AiRunStep(
            id=generate_id("airstep"),
            ai_run_id=ai_run.id,
            step_name=step_name,
            status="running",
            input_json=input_json,
            created_at=datetime.utcnow(),
        )
        db.add(step)
        db.flush()
        try:
            result = func()
            latency_ms = round((perf_counter() - started_at) * 1000)
            step.status = "completed"
            step.output_json = self._compact_step_output(result)
            step.completed_at = datetime.utcnow()
            db.add(step)
            record_agent_event(
                db,
                event_name=_event_name_for_step(step_name, success=True),
                run_type="deck_aistack_orchestration",
                workspace_id=ai_run.workspace_id,
                deck_id=ai_run.deck_id,
                user_id=ai_run.user_id,
                run_id=ai_run.id,
                step_id=step.id,
                status="completed",
                provider=ai_run.provider,
                model=ai_run.model,
                latency_ms=latency_ms,
                metadata=self._telemetry_metadata_for_step(step_name, result),
            )
            db.flush()
            return result
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            step.status = "failed"
            step.error_message = str(exc)
            step.completed_at = datetime.utcnow()
            db.add(step)
            record_agent_event(
                db,
                event_name=_event_name_for_step(step_name, success=False),
                run_type="deck_aistack_orchestration",
                workspace_id=ai_run.workspace_id,
                deck_id=ai_run.deck_id,
                user_id=ai_run.user_id,
                run_id=ai_run.id,
                step_id=step.id,
                event_level="error",
                status="failed",
                provider=ai_run.provider,
                model=ai_run.model,
                latency_ms=latency_ms,
                error_category=_error_category_for_step(step_name, exc),
                error_message=str(exc),
                metadata={"stepName": step_name},
            )
            db.flush()
            raise

    def _compact_step_output(self, result) -> dict:
        if hasattr(result, "model_dump"):
            data = result.model_dump(mode="json", by_alias=True)
        elif isinstance(result, DesignBatch):
            data = {"batchId": result.id, "status": result.status}
        elif isinstance(result, dict):
            if "selectedSlides" in result:
                data = {
                    "deckId": result.get("deck", {}).get("id") if isinstance(result.get("deck"), dict) else None,
                    "selectedSlideIds": result.get("selectedSlideIds", []),
                    "selectedSlideCount": len(result.get("selectedSlides", [])),
                    "hasBrandContext": bool(result.get("brand")),
                }
            else:
                data = result
        else:
            data = {"resultType": result.__class__.__name__}
        return data

    def _telemetry_metadata_for_step(self, step_name: str, result) -> dict:
        if step_name == "build_context" and isinstance(result, dict):
            return {
                "stepName": step_name,
                "selectedSlideCount": len(result.get("selectedSlides", [])),
                "hasBrandContext": bool(result.get("brand")),
            }
        if step_name == "generate_scene_graph" and hasattr(result, "generated_slides"):
            return {
                "stepName": step_name,
                "generatedSlideCount": len(result.generated_slides),
                "batchTitle": getattr(result, "batch_title", None),
            }
        if step_name == "validate_scene_graph" and isinstance(result, dict):
            return {
                "stepName": step_name,
                "valid": result.get("valid"),
                "messageCount": len(result.get("messages", [])) if isinstance(result.get("messages"), list) else 0,
                "messages": result.get("messages", []),
            }
        if step_name == "save_generation_batch" and isinstance(result, DesignBatch):
            return {"stepName": step_name, "batchId": result.id, "status": result.status}
        return {"stepName": step_name}

    def _save_batch(self, db: Session, deck: Deck, request: AiOrchestrationRequest, output, ai_run_id: str) -> DesignBatch:
        deck_with_slides = (
            db.query(Deck)
            .options(selectinload(Deck.slides))
            .filter(Deck.id == deck.id)
            .one()
        )
        slides_by_id = {slide.id: slide for slide in deck_with_slides.slides}
        selected_slides = [slides_by_id[slide_id] for slide_id in request.selected_slide_ids]
        batch_number = db.query(DesignBatch).filter(DesignBatch.deck_id == deck.id).count() + 1
        batch = DesignBatch(
            id=generate_id("batch"),
            deck_id=deck.id,
            batch_number=batch_number,
            batch_name=output.batch_title or f"Iteration {batch_number}",
            scope_type="selected_slides",
            prompt=request.user_instruction.strip(),
            audience_label=request.audience or deck.audience,
            selected_slide_count=len(selected_slides),
            status="completed",
            use_brand_profile=True,
            use_website_context=True,
            use_block_classifications=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(batch)
        db.flush()

        generated_by_slide_id = {slide.source_slide_id: slide for slide in output.generated_slides}
        for source_slide in selected_slides:
            generated = generated_by_slide_id[source_slide.id]
            db.add(
                DesignBatchSlide(
                    id=generate_id("batchslide"),
                    batch_id=batch.id,
                    slide_id=source_slide.id,
                    slide_index_snapshot=source_slide.slide_index,
                    slide_title_snapshot=source_slide.title,
                )
            )
            candidate = GeneratedSlideCandidate(
                id=generate_id("candidate"),
                batch_id=batch.id,
                source_slide_id=source_slide.id,
                slide_index=source_slide.slide_index,
                title=generated.title,
                headline=generated.headline,
                summary=generated.summary,
                status="reviewable",
            )
            db.add(candidate)
            db.flush()
            scene_graph = generated.scene_graph.model_dump(mode="json", by_alias=True)
            db.add(
                DeckLlmArtifact(
                    id=generate_id("artifact"),
                    deck_id=deck.id,
                    artifact_type=GENERATED_SLIDE_ARTIFACT_TYPE,
                    artifact_key=candidate.id,
                    schema_version="smart-deck-scene-graph.v1",
                    status="valid",
                    summary=generated.rationale,
                    payload_json={
                        "generatedSlideId": candidate.id,
                        "batchId": batch.id,
                        "sourceSlideId": source_slide.id,
                        "aiRunId": ai_run_id,
                        "schemaJson": scene_graph,
                        "renderSchema": scene_graph,
                        "sceneGraph": scene_graph,
                        "validationStatus": "valid",
                        "validationMessages": ["valid"],
                        "rationale": generated.rationale,
                    },
                    metrics_json={"aiRunId": ai_run_id, "sourceSlideId": source_slide.id},
                )
            )

        db.flush()
        return batch


def _event_name_for_step(step_name: str, *, success: bool) -> str:
    if step_name == "build_context":
        return "ai.context.built" if success else "ai.context.failed"
    if step_name == "generate_scene_graph":
        return "ai.provider.completed" if success else "ai.provider.failed"
    if step_name == "validate_scene_graph":
        return "ai.validation.completed" if success else "ai.validation.failed"
    if step_name == "save_generation_batch":
        return "ai.persistence.completed" if success else "ai.persistence.failed"
    return "ai.step.completed" if success else "ai.step.failed"


def _error_category_for_step(step_name: str, exc: Exception) -> str:
    if step_name == "build_context":
        return "context_build_failed"
    if step_name == "generate_scene_graph":
        return "provider_invalid_json" if exc.__class__.__name__.endswith("ValidationError") else "provider_failed"
    if step_name == "validate_scene_graph":
        return "scene_graph_validation_failed"
    if step_name == "save_generation_batch":
        return "persistence_failed"
    return _error_category_for_exception(exc)


def _error_category_for_exception(exc: Exception) -> str:
    if isinstance(exc, SceneGraphValidationError):
        return "scene_graph_validation_failed"
    if isinstance(exc, AiOrchestrationError):
        return "context_build_failed"
    return "unknown_error"
