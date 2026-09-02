"""Insight Agent (persona-spec.md § 24 / architecture-assessment.md § E) —
the highest-value, hardest-to-fake output, so it defaults to the higher-
reasoning-budget model (Opus) per TRD § 3.

Must answer one of persona.yml's insight_questions — enforced by requiring
`question_answered` in the output schema (not just hoping the prose does it).
Personal-experience claims are constrained to `knowledge_snippets`, which the
caller must have already filtered to ``knowledge_items.is_public = True``
(brief rule 2) — this agent has no other way to learn about Yahya's history.
"""

from __future__ import annotations

from typing import Callable

from app.agents.contracts import InsightOutput
from app.agents.llm import call_json
from app.config import settings
from app.domain.models import ClusterResult
from app.domain.prompts import build_system_prompt


def _prompt(cluster: ClusterResult, angle: str, knowledge_snippets: list[str],
           insight_questions: list[str]) -> str:
    p = cluster.primary
    knowledge = "\n".join(f"- {k}" for k in knowledge_snippets) or \
        "(no directly relevant personal experience on file — use neutral framing: " \
        "\"this is something companies in our industry should examine\", never invent experience)"
    return f"""Event: {p.title}
Chosen angle: {angle}

Yahya's approved, publishable background (the ONLY source you may cite for
anything personal — never invent a project, a number, or a claim not in this
list):
{knowledge}

Insight questions to choose from (answer exactly ONE, the one this event most
naturally connects to):
{chr(10).join(f'- {q}' for q in insight_questions)}

Write 2-4 sentences of genuine analytical insight — not a summary of the
event, and not generic industry commentary. If you reference personal
experience, it must trace directly to the background list above; otherwise
use neutral third-person framing.

Respond as JSON: {{"insight": "...", "question_answered": "the exact question text you answered"}}"""


def run_insight_agent(cluster: ClusterResult, persona: dict, angle: str,
                      knowledge_snippets: list[str], *, language: str = "en",
                      model: str | None = None, call_fn: Callable | None = None) -> InsightOutput:
    return call_json(
        model=model or settings.anthropic_insight_model,
        system=build_system_prompt(persona, language),
        user=_prompt(cluster, angle, knowledge_snippets, persona["insight_questions"]),
        output_cls=InsightOutput,
        call_fn=call_fn,
    )
