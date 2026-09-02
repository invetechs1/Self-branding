from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.db.base import get_session
from app.repositories.system_config import SystemConfigRepository

router = APIRouter(prefix="/system-config", tags=["system-config"],
                   dependencies=[Depends(require_api_key)])


@router.get("")
def get_system_config(session: Session = Depends(get_session)) -> dict:
    return SystemConfigRepository(session).all()
