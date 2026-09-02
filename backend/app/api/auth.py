"""Single-user API key auth (documented assumption — see app/config.py).

Every non-health route depends on this. Never logs the key itself (brief rule 21
"never log API keys/tokens") — only whether a request was authorized.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key")
