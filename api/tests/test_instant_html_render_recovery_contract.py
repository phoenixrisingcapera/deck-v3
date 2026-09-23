from types import SimpleNamespace

import pytest

from app.services.llm.full_html_generation_service import (
    InstantHtmlCheckpointRecoveryError,
    _publisher_waits_for_render_recovery,
    _rebind_compiler_upgrade_outputs,
    _rebind_compiler_upgrade_recovery_metadata,
)


def _owners(*, nested_id: str | None = None, omit_nested_version: bool = False):
    generation = SimpleNamespace(
        id="job_generation",
        status="completed",
        result_json={"designVersionId": "version_v15", "compilerVersion": "instant-html-compiler.v15"},
    )
    nested = {
        "designVersionId": "version_v15",
        "state": "preview",
        "compilerVersion": "instant-html-compiler.v15",
    }
    if nested_id is not None:
        nested["id"] = nested_id
    if omit_nested_version:
        nested.pop("designVersionId")
    workflow = SimpleNamespace(
        id="job_generation",
        status="completed",
        output_json={"designVersionId": "version_v15", "generationJob": dict(nested)},
    )
    schema = SimpleNamespace(
        status="completed",
        output_json={
            "designVersionId": "version_v15",
            "generationWorkflowJobId": "job_generation",
            "generationJob": dict(nested),
        },
    )
    return generation, workflow, schema


def test_compiler_upgrade_accepts_current_persisted_preview_envelope() -> None:
    generation, workflow, schema = _owners()

    _rebind_compiler_upgrade_outputs(
        generation_job=generation,
        workflow_job=workflow,
        schema_job=schema,
        old_design_version_id="version_v15",
        new_design_version_id="version_v16",
        generated_slide_ids=["slide_1"],
        html_artifact_id="artifact_v16",
        from_compiler_version="instant-html-compiler.v15",
        to_compiler_version="instant-html-compiler.v16",
    )

    assert generation.result_json["designVersionId"] == "version_v16"
    assert workflow.output_json["generationJob"]["designVersionId"] == "version_v16"
    assert schema.output_json["generationJob"]["designVersionId"] == "version_v16"


def test_compiler_upgrade_rejects_conflicting_nested_generation_identity() -> None:
    generation, workflow, schema = _owners(nested_id="job_other")

    with pytest.raises(InstantHtmlCheckpointRecoveryError):
        _rebind_compiler_upgrade_outputs(
            generation_job=generation,
            workflow_job=workflow,
            schema_job=schema,
            old_design_version_id="version_v15",
            new_design_version_id="version_v16",
            generated_slide_ids=["slide_1"],
            html_artifact_id="artifact_v16",
            from_compiler_version="instant-html-compiler.v15",
            to_compiler_version="instant-html-compiler.v16",
        )


def test_compiler_upgrade_accepts_legacy_nested_envelope_without_version_id() -> None:
    generation, workflow, schema = _owners(omit_nested_version=True)

    _rebind_compiler_upgrade_outputs(
        generation_job=generation,
        workflow_job=workflow,
        schema_job=schema,
        old_design_version_id="version_v15",
        new_design_version_id="version_v16",
        generated_slide_ids=["slide_1"],
        html_artifact_id="artifact_v16",
        from_compiler_version="instant-html-compiler.v15",
        to_compiler_version="instant-html-compiler.v16",
    )

    assert workflow.output_json["generationJob"]["designVersionId"] == "version_v16"
    assert schema.output_json["generationJob"]["designVersionId"] == "version_v16"


def test_release_pending_render_recovery_accepts_dependency_blocked_publisher() -> None:
    publisher = SimpleNamespace(
        status="blocked",
        error_code="dependency_failed",
        terminal_reason="dependency_failed",
    )

    assert _publisher_waits_for_render_recovery(publisher, "release_pending") is True


def test_render_recovery_rejects_unrelated_blocked_publisher() -> None:
    publisher = SimpleNamespace(
        status="blocked",
        error_code="worker_timeout",
        terminal_reason="worker_lease_expired",
    )

    assert _publisher_waits_for_render_recovery(publisher, "release_pending") is False


def test_first_compiler_upgrade_initializes_exact_recovery_metadata() -> None:
    attempt = SimpleNamespace(id="attempt_1", outcome_metadata_json={"provider": "openai"})
    old_compilation = SimpleNamespace(
        content_hash="old_compilation_hash",
        compiler_version="instant-html-compiler.v16",
        sanitized_html_artifact_id="artifact_v16",
    )
    new_compilation = SimpleNamespace(
        content_hash="new_compilation_hash",
        compiler_version="instant-html-compiler.v17",
        sanitized_html_artifact_id="artifact_v17",
        provider_attempt_id="attempt_1",
    )
    old_artifact = SimpleNamespace(id="artifact_v16", content_hash="old_artifact_hash")
    new_artifact = SimpleNamespace(id="artifact_v17", content_hash="new_artifact_hash")

    _rebind_compiler_upgrade_recovery_metadata(
        attempt=attempt,
        old_design_version_id="version_v16",
        new_design_version_id="version_v17",
        old_compilation=old_compilation,
        new_compilation=new_compilation,
        old_artifact=old_artifact,
        new_artifact=new_artifact,
    )

    recovery = attempt.outcome_metadata_json["checkpointRecovery"]
    assert recovery["designVersionId"] == "version_v17"
    assert recovery["providerAttemptId"] == "attempt_1"
    assert recovery["sanitizedArtifactId"] == "artifact_v17"
    assert recovery["providerCallExecuted"] is False
