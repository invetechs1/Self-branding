"""Strict pydantic I/O contracts for every LLM-backed agent
(architecture-assessment.md § E). Each agent module parses the model's raw
text into one of these ``*Output`` models — on parse failure it retries once
with a stricter instruction, then raises. LLM output never reaches a caller
unvalidated.
"""

from __future__ import annotations

from pydantic import BaseModel


class AgentMeta(BaseModel):
    model: str
    model_version: str
    latency_ms: int
    trace_id: str


class VerifyOutput(BaseModel):
    agreed_facts: list[str]
    flags: list[str] = []
    meta: AgentMeta


class AngleOutput(BaseModel):
    angle: str
    why_it_matters: str
    meta: AgentMeta


class InsightOutput(BaseModel):
    insight: str
    question_answered: str
    meta: AgentMeta


class WriterOutput(BaseModel):
    hook: str
    body: str
    media_brief: str | None = None
    meta: AgentMeta
