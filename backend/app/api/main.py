"""FastAPI app entrypoint.

    uvicorn app.api.main:app --reload

Routers are thin — no business logic here (brief's anti-pattern list explicitly
forbids business logic in controllers). Each router calls a repository directly
for now; once services/ exists (Phase 2+), routers call services, services call
repositories.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routers import (auth, discovery, drafts, intelligence, performance, settings,
                             sources, system_config)

app = FastAPI(title="Yahya AI Content Intelligence Platform", version="0.1.0")

app.include_router(sources.router)
app.include_router(system_config.router)
app.include_router(intelligence.router)
app.include_router(drafts.router)
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(performance.router)
app.include_router(discovery.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
