from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.services.visualizer.workspace_dashboard_read_model import (
    get_workspace_dashboard,
    get_workspace_dashboard_notifications,
    get_workspace_dashboard_tasks,
)

router = APIRouter(prefix="/workspace", tags=["workspace-dashboard"])


@router.get("/dashboard")
def workspace_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return get_workspace_dashboard(db, current_user)


@router.get("/dashboard/notifications")
def workspace_dashboard_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return get_workspace_dashboard_notifications(db, current_user)


@router.get("/dashboard/tasks")
def workspace_dashboard_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return get_workspace_dashboard_tasks(db, current_user)
