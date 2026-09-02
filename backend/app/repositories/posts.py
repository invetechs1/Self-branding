"""Repository for `posts` — drafts through published content, one table with a
status lifecycle (architecture-assessment.md § K.3, § D1). Exposes the
draft/publish split as query filters, not separate tables.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApprovalDecision, Post

RED_CONFIRM_ERROR = ("red-level drafts require explicit human sign-off — "
                     "pass confirmed_red=True to approve one")


class PostRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_draft(self, **kwargs) -> Post:
        post = Post(status="pending_review", **kwargs)
        self.session.add(post)
        self.session.flush()
        return post

    def get(self, post_id: uuid.UUID) -> Post | None:
        return self.session.get(Post, post_id)

    def list_drafts(self, *, platform: str | None = None, safety: str | None = None) -> list[Post]:
        # Everything still actionable from the review queue: not yet decided
        # (draft/pending_review), or decided but not yet published (approved/
        # scheduled/failed — the Drafts screen's action bar renders a "Publish
        # now" / retry button for each of these). Excludes 'rejected' (done,
        # discarded) and 'posted' (done, tracked on the Performance screen).
        stmt = select(Post).where(Post.status.in_(
            ["draft", "pending_review", "approved", "scheduled", "failed"]))
        if platform:
            stmt = stmt.where(Post.platform == platform)
        if safety:
            stmt = stmt.where(Post.approval_level == safety)
        stmt = stmt.order_by(Post.relevance.desc().nullslast(), Post.created_at.desc())
        return list(self.session.scalars(stmt))

    def list_rejected(self, *, platform: str | None = None, limit: int = 100) -> list[Post]:
        """Archive view — rejected drafts (manual rejections and regenerate's
        auto-supersede) are never deleted, just excluded from the active queue."""
        stmt = select(Post).where(Post.status == "rejected")
        if platform:
            stmt = stmt.where(Post.platform == platform)
        stmt = stmt.order_by(Post.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def recent_bodies(self, limit: int = 60) -> list[str]:
        stmt = select(Post.body).order_by(Post.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    # ── approval decisions (brief rule 5: RED never auto-approved) ──

    def approve(self, post_id: uuid.UUID, *, decided_by: str = "yahya",
               confirmed_red: bool = False) -> Post:
        post = self._require(post_id)
        if post.approval_level == "red" and not confirmed_red:
            raise ValueError(RED_CONFIRM_ERROR)
        post.status = "approved"
        self.session.add(ApprovalDecision(post_id=post.id, decision="approved", decided_by=decided_by))
        return post

    def edit_and_approve(self, post_id: uuid.UUID, new_body: str, *, decided_by: str = "yahya",
                         confirmed_red: bool = False) -> Post:
        post = self._require(post_id)
        if post.approval_level == "red" and not confirmed_red:
            raise ValueError(RED_CONFIRM_ERROR)
        edit_diff = f"--- before ---\n{post.body}\n--- after ---\n{new_body}"
        post.body = new_body
        post.status = "approved"
        self.session.add(ApprovalDecision(post_id=post.id, decision="edited", edit_diff=edit_diff,
                                          decided_by=decided_by))
        return post

    def reject(self, post_id: uuid.UUID, reason_tags: list[str], *, comment: str | None = None,
              decided_by: str = "yahya") -> Post:
        post = self._require(post_id)
        post.status = "rejected"
        self.session.add(ApprovalDecision(post_id=post.id, decision="rejected", edit_diff=comment,
                                          reason_tags=reason_tags, decided_by=decided_by))
        return post

    def supersede(self, post_id: uuid.UUID, *, reason: str = "regenerated") -> Post:
        """Marks a draft as replaced by a newer generation, keeping the audit trail
        instead of deleting the row."""
        post = self._require(post_id)
        post.status = "rejected"
        self.session.add(ApprovalDecision(post_id=post.id, decision="rejected",
                                          reason_tags=["regenerated"], edit_diff=reason,
                                          decided_by="system"))
        return post

    def _require(self, post_id: uuid.UUID) -> Post:
        post = self.get(post_id)
        if post is None:
            raise ValueError(f"unknown post: {post_id}")
        return post
