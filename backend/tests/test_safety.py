"""Safety Agent tests — the brief's non-negotiable rules 1, 2, 4, 5 must hold here,
since this is the deterministic gate no LLM output is allowed to override."""

from app.domain.safety import classify_approval, mix_deficit, violates_personal_experience_rule


def test_prediction_is_classified_yellow(persona):
    level, reasons = classify_approval("أتوقع أن يصبح هذا معياراً خلال ثلاث سنوات", persona, 1.0)
    assert level == "yellow"
    assert reasons


def test_financial_sensitive_content_is_classified_red(persona):
    level, _ = classify_approval("إيرادات الشركة وأرباحها", persona)
    assert level == "red"


def test_low_fact_confidence_forces_red(persona):
    level, reasons = classify_approval("An interesting industry update.", persona, fact_conf=0.3)
    assert level == "red"
    assert any("confidence" in r for r in reasons)


def test_verified_educational_content_is_green(persona):
    level, reasons = classify_approval(
        "How Building Information Modeling reduces rework on infrastructure projects.", persona, 1.0)
    assert level == "green"
    assert reasons == []


def test_unattributed_first_person_claim_violates_experience_rule():
    facts = {"ventures": {"items": [{"name": "Azoom United Contracting"}]}}
    assert violates_personal_experience_rule("In my company we deployed a new system last year.", facts)


def test_first_person_claim_about_a_real_venture_is_allowed():
    facts = {"ventures": {"items": [{"name": "Azoom United Contracting"}]}}
    text = "In Azoom United Contracting we deployed a new cost-control workflow last year."
    assert not violates_personal_experience_rule(text, facts)


def test_mix_deficit_prioritizes_underrepresented_pillar(persona):
    order = mix_deficit({"ai_technology": 10}, persona)
    assert order[0] != "ai_technology"
