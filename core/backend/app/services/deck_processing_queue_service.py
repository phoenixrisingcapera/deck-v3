from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def queue_workflow_job(
    db: Session,
    *,
    deck_id: str,
    job_type: str,
    workflow_execution_mode: str = "compatibility_projection_only",
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "workflowExecutionMode": workflow_execution_mode,
        "compatibility_projection_only": True,
    }
