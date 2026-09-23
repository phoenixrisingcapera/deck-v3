from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProcessingJobResponse(BaseModel):
    """Single workflow job for admin dashboard."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    deck_id: str
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None
    extraction_run_id: Optional[str] = None
    job_type: str
    status: str
    priority: int
    idempotency_key: Optional[str] = None
    attempt_count: int
    max_attempts: int
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class ProcessingDashboardResponse(BaseModel):
    """List of processing jobs with pagination."""
    jobs: list[ProcessingJobResponse]
    total: int
    limit: int
    offset: int


class ProcessingStatsResponse(BaseModel):
    """Aggregate statistics for processing jobs."""
    total_jobs: int
    status_counts: dict[str, int]
    job_type_counts: dict[str, int]
    stuck_jobs: int
