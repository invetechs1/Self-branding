"""Drafts & Approval endpoints — architecture-assessment.md § F2, the highest-
priority screen. Journeys 2-4: review -> approve/edit/reject -> auto-advance
(auto-advance is a frontend concern; this API just needs each action to be a
single fast call)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_key
from app.api.schemas import SourceOut, source_lookup
from app.db.base import get_session
from app.repositories.clusters import StoryClusterRepository
from app.repositories.posts import PostRepository
from app.services.generation import generate_draft_for_cluster, regenerate_draft
from app.services.publishing import publish_draft

router = APIRouter(prefix="/drafts", tags=["drafts"], dependencies=[Depends(require_api_key)])


class DraftOut(BaseModel):
    id: uuid.UUID
    platform: str
    language: str
    pillar: str | None
    hook: str | None
    body: str
    media_brief: str | None
    approval_level: str
    review_notes: str | None
    fact_confidence: float | None
    relevance: float | None
    status: str
    external_id: str | None = None
    scores: dict | None = None
    sources: list[SourceOut] = []


class GenerateRequest(BaseModel):
    cluster_id: uuid.UUID
    platform: str
    language: str | None = None


class ApproveRequest(BaseModel):
    confirmed_red: bool = False


class EditApproveRequest(BaseModel):
    body: str
    confirmed_red: bool = False


class RejectRequest(BaseModel):
    reason_tags: list[str]
    comment: str | None = None


class RegenerateRequest(BaseModel):
    mode: str = "full"


def _to_out(post, session: Session) -> DraftOut:
    scores: dict | None = None
    sources: list[SourceOut] = []
    if post.cluster_id is not None:
        cluster_repo = StoryClusterRepository(session)
        cluster = cluster_repo.get(post.cluster_id)
        if cluster is not None:
            articles = cluster_repo.articles_of(post.cluster_id)
            primary = next((a for a in articles if a.id == cluster.primary_article_id), None) \
                or (articles[0] if articles else None)
            scores = primary.scores if primary else None
            lookup = source_lookup(session, articles)
            sources = list(lookup.values())

    return DraftOut(id=post.id, platform=post.platform, language=post.language, pillar=post.pillar,
                    hook=post.hook, body=post.body, media_brief=post.media_brief,
                    approval_level=post.approval_level, review_notes=post.review_notes,
                    fact_confidence=float(post.fact_confidence) if post.fact_confidence is not None else None,
                    relevance=float(post.relevance) if post.relevance is not None else None,
                    status=post.status, external_id=post.external_id, scores=scores, sources=sources)


@router.get("", response_model=list[DraftOut])
def list_drafts(platform: str | None = None, safety: str | None = None,
                session: Session = Depends(get_session)) -> list[DraftOut]:
    posts = PostRepository(session).list_drafts(platform=platform, safety=safety)
    return [_to_out(p, session) for p in posts]


class RejectedDraftOut(DraftOut):
    rejected_at: str | None = None
    reason_tags: list[str] = []
    comment: str | None = None
    rejected_by: str | None = None


@router.get("/rejected", response_model=list[RejectedDraftOut])
def list_rejected(platform: str | None = None, session: Session = Depends(get_session)) -> list[RejectedDraftOut]:
    """Archive view for the Drafts screen's "Rejected" tab — nothing is ever
    deleted, this is just excluded from the default active-queue list."""
    posts = PostRepository(session).list_rejected(platform=platform)
    out = []
    for p in posts:
        base = _to_out(p, session)
        last_decision = max((a for a in p.approvals if a.decision == "rejected"),
                            key=lambda a: a.decided_at, default=None)
        out.append(RejectedDraftOut(
            **base.model_dump(),
            rejected_at=last_decision.decided_at.isoformat() if last_decision else None,
            reason_tags=last_decision.reason_tags if last_decision else [],
            comment=last_decision.edit_diff if last_decision else None,
            rejected_by=last_decision.decided_by if last_decision else None,
        ))
    return out


@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: uuid.UUID, session: Session = Depends(get_session)) -> DraftOut:
    post = PostRepository(session).get(draft_id)
    if post is None:
        raise HTTPException(status_code=404, detail="draft not found")
    return _to_out(post, session)


@router.post("/generate", response_model=DraftOut)
def generate(body: GenerateRequest, session: Session = Depends(get_session)) -> DraftOut:
    try:
        post = generate_draft_for_cluster(session, body.cluster_id, body.platform, language=body.language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    session.commit()
    return _to_out(post, session)


@router.post("/{draft_id}/approve", response_model=DraftOut)
def approve(draft_id: uuid.UUID, body: ApproveRequest, session: Session = Depends(get_session)) -> DraftOut:
    try:
        post = PostRepository(session).approve(draft_id, confirmed_red=body.confirmed_red)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return _to_out(post, session)


@router.post("/{draft_id}/edit-approve", response_model=DraftOut)
def edit_approve(draft_id: uuid.UUID, body: EditApproveRequest,
                 session: Session = Depends(get_session)) -> DraftOut:
    try:
        post = PostRepository(session).edit_and_approve(draft_id, body.body,
                                                         confirmed_red=body.confirmed_red)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return _to_out(post, session)


@router.post("/{draft_id}/reject", response_model=DraftOut)
def reject(draft_id: uuid.UUID, body: RejectRequest, session: Session = Depends(get_session)) -> DraftOut:
    try:
        post = PostRepository(session).reject(draft_id, body.reason_tags, comment=body.comment)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    session.commit()
    return _to_out(post, session)


@router.post("/{draft_id}/regenerate", response_model=DraftOut)
def regenerate(draft_id: uuid.UUID, body: RegenerateRequest,
               session: Session = Depends(get_session)) -> DraftOut:
    try:
        post = regenerate_draft(session, draft_id, mode=body.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    session.commit()
    return _to_out(post, session)


@router.post("/{draft_id}/publish", response_model=DraftOut)
def publish(draft_id: uuid.UUID, session: Session = Depends(get_session)) -> DraftOut:
    """Manual publish trigger — a human clicks this after approval. Idempotent:
    calling it again on an already-posted draft is a safe no-op (see
    app.services.publishing.publish_draft). Instagram/TikTok/article stay
    'scheduled' (manual publish) since no automated path exists for them yet."""
    try:
        post = publish_draft(session, draft_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    session.commit()
    return _to_out(post, session)
