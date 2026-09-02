"""Verify Agent (TRD § 22 / architecture-assessment.md § E).

The AUTHORITATIVE fact-confidence number stays deterministic
(``domain.clustering.fact_confidence``, already computed on the cluster before
this agent ever runs) — this agent only extracts which claims the sources
actually agree on, so the Writer agent has a grounded fact list to work from.
It cannot raise or lower the cluster's confidence score.
"""

from __future__ import annotations

from typing import Callable

from app.agents.contracts import VerifyOutput
from app.agents.llm import call_json
from app.config import settings
from app.domain.models import ClusterResult


def _prompt(cluster: ClusterResult) -> str:
    sources = "\n".join(f"- {m.source} ({m.source_type}): {m.title}\n  {m.summary}"
                        for m in cluster.members)
    return f"""Here are {cluster.source_count} report(s) of the same event:

{sources}

Extract ONLY the facts that are consistent across these reports (dates, names,
numbers, what actually happened). Do not add anything not stated in the text
above. Flag anything that looks inconsistent between sources.

Respond as JSON: {{"agreed_facts": ["..."], "flags": ["..."]}}"""


def run_verify_agent(cluster: ClusterResult, persona: dict, *, language: str = "en",
                     model: str | None = None, call_fn: Callable | None = None) -> VerifyOutput:
    from app.domain.prompts import build_system_prompt

    return call_json(
        model=model or settings.anthropic_model,
        system=build_system_prompt(persona, language),
        user=_prompt(cluster),
        output_cls=VerifyOutput,
        call_fn=call_fn,
    )
