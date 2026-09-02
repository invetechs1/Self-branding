"""Thin Anthropic client wrapper — the only place ``anthropic`` is imported.

Every agent calls through ``complete()``, never the SDK directly, so that:
  - tests can inject a fake ``call_fn`` and never hit the network (brief's
    testing rule: "LLM tests should use deterministic mocks/fixtures").
  - model/version/latency metadata is captured uniformly for every agent call
    (architecture-assessment.md § E contract: every agent output carries
    model, model_version, latency_ms, trace_id).
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from app.config import settings


class LLMCallable(Protocol):
    def __call__(self, *, model: str, system: str, user: str, max_tokens: int) -> str: ...


@dataclass
class LLMResult:
    text: str
    model: str
    model_version: str
    latency_ms: int
    trace_id: str


def _default_call(*, model: str, system: str, user: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                 messages=[{"role": "user", "content": user}])
    # content[0] isn't reliably the text block — models that emit extended
    # thinking put a ThinkingBlock first, so scan for the actual text block.
    for block in msg.content:
        if block.type == "text":
            return block.text.strip()
    raise RuntimeError(f"no text block in Anthropic response: {msg.content!r}")


def complete(*, model: str, system: str, user: str, max_tokens: int = 2000,
            call_fn: Callable | None = None) -> LLMResult:
    """One LLM call with uniform metadata. `call_fn` defaults to the real
    Anthropic API; tests inject a fake returning canned text instantly."""
    call_fn = call_fn or _default_call
    trace_id = str(uuid.uuid4())
    started = time.monotonic()
    text = call_fn(model=model, system=system, user=user, max_tokens=max_tokens)
    latency_ms = int((time.monotonic() - started) * 1000)
    return LLMResult(text=text, model=model, model_version=model, latency_ms=latency_ms,
                     trace_id=trace_id)


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class AgentOutputError(RuntimeError):
    """Raised when an agent's LLM output fails schema validation twice.
    Callers must not silently fall back to unvalidated text (brief rule 16:
    LLM output never controls business logic without deterministic validation)."""


def call_json(*, model: str, system: str, user: str, output_cls, max_tokens: int = 2000,
              call_fn: Callable | None = None):
    """Calls the LLM expecting a single JSON object matching `output_cls`
    (minus its `meta` field, filled in here). Retries once with a stricter
    instruction on parse/validation failure; raises AgentOutputError if the
    second attempt also fails — never returns unvalidated output."""
    json_instruction = ("\n\nRespond with ONLY a single valid JSON object — no prose before or "
                        "after, no markdown code fences.")
    last_error: Exception | None = None

    for attempt in range(2):
        prompt = user + json_instruction + ("" if attempt == 0 else
            "\n\nYour previous response was not valid JSON. Output ONLY the JSON object this time.")
        result = complete(model=model, system=system, user=prompt, max_tokens=max_tokens, call_fn=call_fn)
        match = _JSON_BLOCK.search(result.text)
        if not match:
            last_error = ValueError(f"no JSON object found in response: {result.text[:200]!r}")
            continue
        try:
            data = json.loads(match.group(0))
            data["meta"] = {"model": result.model, "model_version": result.model_version,
                            "latency_ms": result.latency_ms, "trace_id": result.trace_id}
            return output_cls.model_validate(data)
        except Exception as e:  # noqa: BLE001 — any parse/validation failure triggers the retry
            last_error = e
            continue

    raise AgentOutputError(f"agent output failed validation after 2 attempts: {last_error}")
