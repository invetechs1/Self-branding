"""Writer Agent (persona-spec.md § 27-32 / architecture-assessment.md § E).

Platform length/structure rules are enforced deterministically by the caller
after generation (truncate/flag, never "hope the model followed instructions")
— this agent's job is just to produce the best draft against the platform
brief in `persona.yml -> platforms`.
"""

from __future__ import annotations

from typing import Callable

from app.agents.contracts import WriterOutput
from app.agents.llm import call_json
from app.config import settings
from app.domain.prompts import build_system_prompt


def _platform_spec(persona: dict, platform: str) -> str:
    spec = persona["platforms"].get(platform, {})
    parts = [f"Length: {spec.get('length', '')}"]
    if spec.get("structure"):
        parts.append("Structure: " + " -> ".join(spec["structure"]))
    if spec.get("style"):
        parts.append("Style: " + spec["style"])
    if platform == "twitter_thread":
        parts.append("Separate tweets with a line containing only ---.")
    return " | ".join(parts)


def _prompt(angle: str, why_it_matters: str, insight: str, platform: str, persona: dict,
           knowledge_snippets: list[str]) -> str:
    knowledge = "\n".join(f"- {k}" for k in knowledge_snippets) or "(none)"
    return f"""Angle: {angle}
Why it matters: {why_it_matters}
Insight: {insight}

Approved personal background you may draw on (nothing outside this list):
{knowledge}

Write for {platform}. {_platform_spec(persona, platform)}

Forbidden: summarizing a source article verbatim, inventing any number or
personal achievement, unnecessary hashtags, presenting a prediction as fact.

Respond as JSON: {{"hook": "the opening line/headline", "body": "the full post text",
"media_brief": "one line describing any visual needed, or null"}}"""


def run_writer_agent(angle: str, why_it_matters: str, insight: str, platform: str, persona: dict,
                     knowledge_snippets: list[str], *, language: str = "en",
                     model: str | None = None, call_fn: Callable | None = None) -> WriterOutput:
    return call_json(
        model=model or settings.anthropic_model,
        system=build_system_prompt(persona, language),
        user=_prompt(angle, why_it_matters, insight, platform, persona, knowledge_snippets),
        output_cls=WriterOutput,
        call_fn=call_fn,
    )
