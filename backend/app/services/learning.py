"""Learning service — orchestrates the recompute: read performance +
approvals -> domain.learning.compute_weights -> write pillars.multiplier +
a learning_weights snapshot. This is what powers `score_article`'s
`learning` multiplier on the next discovery cycle (architecture-assessment.md
§ C: the learning loop closes here)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.learning import compute_weights
from app.repositories.learning import LearningRepository
from app.repositories.metrics import MetricsRepository
from app.repositories.persona import PersonaRepository


def recompute_learning_weights(session: Session) -> dict:
    persona_repo = PersonaRepository(session)
    pillars = [p.key for p in persona_repo.list_pillars()]
    if not pillars:
        raise RuntimeError("no pillars in database — run scripts/seed.py first")

    metrics_repo = MetricsRepository(session)
    learning_repo = LearningRepository(session)

    metric_rows = metrics_repo.rows_with_pillar()
    decisions = learning_repo.decisions_with_pillar()

    weights, detail = compute_weights(metric_rows, decisions, pillars)

    for pillar, multiplier in weights.items():
        persona_repo.set_pillar_multiplier(pillar, multiplier)

    sample_size = len(metric_rows) + len(decisions)
    learning_repo.save_snapshot(weights, detail, sample_size)

    return {"weights": weights, "detail": detail, "sample_size": sample_size}
