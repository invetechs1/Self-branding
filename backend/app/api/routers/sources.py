from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.db.base import get_session
from app.repositories.sources import SourceRepository

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_api_key)])


class SourceOut(BaseModel):
    id: int
    name: str
    url: str
    source_type: str
    credibility: int
    region: str | None
    enabled: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_session)) -> list[SourceOut]:
    return list(SourceRepository(session).list_enabled())
