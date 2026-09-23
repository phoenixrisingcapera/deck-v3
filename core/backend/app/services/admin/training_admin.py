from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Workspace


def update_workspace_training_policy(
    db: Session,
    workspace_id: str,
    *,
    allow_model_training: bool,
    model_training_policy: str,
) -> dict | None:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).one_or_none()
    if workspace is None:
        return None
    workspace.allow_model_training = allow_model_training
    workspace.model_training_policy = model_training_policy.strip() or ("internal_only" if allow_model_training else "disabled")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return {
        "workspaceId": workspace.id,
        "allowModelTraining": workspace.allow_model_training,
        "modelTrainingPolicy": workspace.model_training_policy,
    }
