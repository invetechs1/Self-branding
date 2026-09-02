"""Angle Agent (persona-spec.md § 23-24 / architecture-assessment.md § E).

Picks exactly ONE angle for a cluster — enforced by the output schema being a
single string, not a list, matching the brief's originality rule
("choose ONE angle, not five posts").
"""

from __future__ import annotations

from typing import Callable

from app.agents.contracts import AngleOutput
from app.agents.llm import call_json
from app.config import settings
from app.domain.models import ClusterResult
from app.domain.prompts import build_system_prompt

ANGLE_OPTIONS = ["business opportunity", "impact on construction", "impact on real estate",
                 "AI opportunity", "relevance to the Saudi market", "productivity impact",
                 "new business model", "competitive threat"]


def _prompt(cluster: ClusterResult, verified_facts: list[str], pillar: str) -> str:
    p = cluster.primary
    facts = "\n".join(f"- {f}" for f in verified_facts) or "(none extracted)"
    return f"""Event: {p.title}
Summary: {p.summary}
Content pillar: {pillar}

Verified facts:
{facts}

Choose exactly ONE angle from: {', '.join(ANGLE_OPTIONS)}.
Never simply summarize the event — pick the single most interesting angle for
an entrepreneur/engineer audience and explain briefly why it matters to Yahya
specifically (not why it matters "to the industry" in generic terms).

Respond as JSON: {{"angle": "one short sentence naming the chosen angle",
"why_it_matters": "2-3 sentences, specific, no generic filler"}}"""


def run_angle_agent(cluster: ClusterResult, persona: dict, verified_facts: list[str], *,
                    pillar: str | None = None, language: str = "en", model: str | None = None,
                    call_fn: Callable | None = None) -> AngleOutput:
    pillar = pillar or cluster.primary.meta.get("pillar", "ai_technology")
    return call_json(
        model=model or settings.anthropic_model,
        system=build_system_prompt(persona, language),
        user=_prompt(cluster, verified_facts, pillar),
        output_cls=AngleOutput,
        call_fn=call_fn,
    )
