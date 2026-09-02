"""Login endpoint. Reachable only from the Next.js server (which already
carries X-API-Key via the proxy pattern — the browser never calls this
directly), so it stays behind the same `require_api_key` dependency as every
other router for consistency. Human identity (which user is logged in) is a
separate layer the frontend owns via its own signed session cookie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.db.base import get_session
from app.repositories.users import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(require_api_key)])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    email: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    user = UserRepository(session).authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    session.commit()
    return LoginResponse(email=user.email)
