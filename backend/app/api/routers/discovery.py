"""Manual "fetch latest" trigger for Today's Intelligence. Discovery normally
runs on a schedule (cron/Task Scheduler calling scripts/discover.py every 3
hours — see docs/technical-requirements.md § 7); this lets a human ask for it
now from the dashboard, without blocking the HTTP request for the ~60-90s a
full cycle takes (17 RSS fetches).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.db.base import SessionLocal, get_session
from app.repositories.system_config import SystemConfigRepository
from app.services.discovery import run_discovery_in_background

router = APIRouter(prefix="/discover", tags=["discovery"], dependencies=[Depends(require_api_key)])


class DiscoveryStatusOut(BaseModel):
    status: str  # idle|running|error
    started_at: str | None = None
    completed_at: str | None = None
    last_result: dict | None = None
    error: str | None = None


@router.get("/status", response_model=DiscoveryStatusOut)
def get_status(session: Session = Depends(get_session)) -> DiscoveryStatusOut:
    cfg = SystemConfigRepository(session)
    return DiscoveryStatusOut(
        status=cfg.get("discovery_status", "idle"),
        started_at=cfg.get("discovery_started_at"),
        completed_at=cfg.get("discovery_completed_at"),
        last_result=cfg.get("discovery_last_result"),
        error=cfg.get("discovery_error"),
    )


@router.post("/run", response_model=DiscoveryStatusOut, status_code=202)
def trigger_discovery(background_tasks: BackgroundTasks,
                      session: Session = Depends(get_session)) -> DiscoveryStatusOut:
    cfg = SystemConfigRepository(session)
    if cfg.get("discovery_status") == "running":
        raise HTTPException(status_code=409, detail="a discovery cycle is already running")

    background_tasks.add_task(run_discovery_in_background, SessionLocal)
    return DiscoveryStatusOut(status="running")
