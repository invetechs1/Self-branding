"""Agent contract tests — no network, ever. Each agent gets a fake `call_fn`
returning canned text, per the brief's "deterministic mocks/fixtures" rule."""

import json

import pytest

from app.agents.angle import run_angle_agent
from app.agents.insight import run_insight_agent
from app.agents.llm import AgentOutputError, call_json
from app.agents.verify import run_verify_agent
from app.agents.writer import run_writer_agent
from app.agents.contracts import AngleOutput
from app.domain.clustering import cluster_articles
from app.domain.models import Article, utcnow
from app.domain.scoring import score_article


def _fake_call(json_text):
    def fn(*, model, system, user, max_tokens):
        return json_text
    return fn


def _sample_cluster(persona):
    now = utcnow()
    a = Article(title="Saudi PIF backs AI construction monitoring startup with $40 million to expand in Riyadh",
               summary="The funding round targets computer vision progress tracking for contractors.",
               url="https://example.test/1", source="Test", source_type="major_international_publication",
               published=now)
    score_article(a, persona, now)
    return cluster_articles([a], persona)[0]


def test_verify_agent_parses_valid_json(persona):
    call_fn = _fake_call(json.dumps({"agreed_facts": ["$40 million round", "Riyadh expansion"],
                                     "flags": []}))
    out = run_verify_agent(_sample_cluster(persona), persona, call_fn=call_fn)
    assert out.agreed_facts == ["$40 million round", "Riyadh expansion"]
    assert out.meta.trace_id


def test_angle_agent_parses_valid_json(persona):
    call_fn = _fake_call(json.dumps({"angle": "AI opportunity", "why_it_matters": "Because X."}))
    out = run_angle_agent(_sample_cluster(persona), persona, ["$40 million round"], call_fn=call_fn)
    assert out.angle == "AI opportunity"


def test_insight_agent_parses_valid_json(persona):
    call_fn = _fake_call(json.dumps({
        "insight": "This validates AI monitoring as a real cost lever for contractors.",
        "question_answered": persona["insight_questions"][0],
    }))
    out = run_insight_agent(_sample_cluster(persona), persona, "AI opportunity",
                            ["Azoom United Contracting: founder and CEO"], call_fn=call_fn)
    assert out.question_answered == persona["insight_questions"][0]


def test_writer_agent_parses_valid_json(persona):
    call_fn = _fake_call(json.dumps({
        "hook": "Construction just got a $40M reason to take AI seriously.",
        "body": "Full post body here.",
        "media_brief": None,
    }))
    out = run_writer_agent("AI opportunity", "Because X.", "This validates Y.", "linkedin_post",
                           persona, [], call_fn=call_fn)
    assert "40M" in out.hook
    assert out.media_brief is None


def test_call_json_retries_once_then_raises_on_persistent_garbage():
    call_fn = _fake_call("this is not json at all")
    with pytest.raises(AgentOutputError):
        call_json(model="test", system="s", user="u", output_cls=AngleOutput, call_fn=call_fn)


def test_call_json_recovers_if_second_attempt_is_valid():
    attempts = {"n": 0}

    def call_fn(*, model, system, user, max_tokens):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "garbage, not json"
        return json.dumps({"angle": "AI opportunity", "why_it_matters": "Because X."})

    out = call_json(model="test", system="s", user="u", output_cls=AngleOutput, call_fn=call_fn)
    assert out.angle == "AI opportunity"
    assert attempts["n"] == 2


def test_call_json_extracts_json_even_with_surrounding_prose():
    call_fn = _fake_call('Here is the result:\n{"angle": "AI opportunity", "why_it_matters": "Because X."}\nHope that helps!')
    out = call_json(model="test", system="s", user="u", output_cls=AngleOutput, call_fn=call_fn)
    assert out.angle == "AI opportunity"
