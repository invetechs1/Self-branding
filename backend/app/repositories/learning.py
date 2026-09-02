"""Repository for `learning_weights` and `approval_decisions` reads used by
the learning engine and the Performance & Learning screen."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApprovalDecision, LearningWeight, Post


class LearningRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_snapshot(self, weights: dict, detail: dict, sample_size: int) -> LearningWeight:
        row = LearningWeight(weights={"pillar_multipliers": weights, "detail": detail},
                             sample_size=sample_size)
        self.session.add(row)
        return row

    def latest(self) -> LearningWeight | None:
        stmt = select(LearningWeight).order_by(LearningWeight.computed_at.desc()).limit(1)
        return self.session.scalar(stmt)

    def decisions_with_pillar(self) -> list[dict]:
        stmt = (select(ApprovalDecision.decision, Post.pillar)
               .join(Post, Post.id == ApprovalDecision.post_id))
        return [{"decision": d, "pillar": p} for d, p in self.session.execute(stmt)]

    def approval_counts(self) -> tuple[int, int]:
        """(approved_or_edited, rejected) across all decisions."""
        approved = rejected = 0
        for decision, in self.session.execute(select(ApprovalDecision.decision)):
            if decision in ("approved", "edited"):
                approved += 1
            elif decision == "rejected":
                rejected += 1
        return approved, rejected
