"""The backend classifier, profile/persona.yml and the database must agree on content pillars.

posts.pillar / raw_articles.pillar / trends.pillar are foreign keys to pillars.key, so a pillar
the classifier emits that the persona does not define makes the write fail (a 500 on "Create
draft", or an aborted discovery run). These tests pin the contract end to end, against the real
persona.yml and a real Postgres, and check that rows left over from an older persona are never
modified or deleted.
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seed as seed_script  # noqa: E402

from app.db.models import Pillar, Post, RawArticle
from app.domain.models import Article
from app.domain.scoring import PILLAR_TERMS, pillars_ranked
from app.repositories.articles import RawArticleRepository
from app.repositories.opportunities import TrendRepository
from app.repositories.persona import PersonaRepository
from app.repositories.posts import PostRepository

ROOT = Path(__file__).resolve().parents[2]


def _persona_yaml() -> dict:
    return seed_script.yaml.safe_load(seed_script.PERSONA_PATH.read_text(encoding="utf-8"))


def _seed_real_persona(db_session) -> PersonaRepository:
    repo = PersonaRepository(db_session)
    seed_script.seed_persona(repo, _persona_yaml())
    db_session.flush()
    return repo


def _article(text: str) -> Article:
    return Article(title=text, summary="", url="https://example.com/x", source="1", language="ar",
                   published=datetime.now(timezone.utc), scores={}, meta={})


# ── contract: classifier == persona ─────────────────────────────────────────

def test_classifier_pillars_are_exactly_the_configured_pillars():
    configured = set(_persona_yaml()["content_pillars"])
    assert set(PILLAR_TERMS) == configured


def test_pillar_shares_sum_to_100_percent():
    shares = [spec["share"] for spec in _persona_yaml()["content_pillars"].values()]
    assert sum(shares) == pytest.approx(1.0)


def test_classifier_terms_match_the_automation_cli():
    """The backend classifier is a port of automation/persona.py — fail loudly if they drift."""
    spec = importlib.util.spec_from_file_location("automation_persona", ROOT / "automation" / "persona.py")
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules["automation_persona"] = module
        spec.loader.exec_module(module)
    except Exception as e:  # noqa: BLE001 — automation deps not installed in this environment
        pytest.skip(f"automation/persona.py not importable here: {e}")
    assert PILLAR_TERMS == module.PILLAR_TERMS


# every configured pillar must be reachable by the classifier from realistic Arabic text
SAMPLES = {
    "construction_projects": "ترسية مناقصة مشروع إنشائي على مقاول الباطن وتأخر المشروع وغرامة تأخير",
    "ai_technology": "إطلاق وكيل ذكاء اصطناعي ونموذج لغوي لأتمتة الأعمال وتعلم آلي",
    "government_decisions": "وزارة الموارد البشرية تعلن قرار وزاري جديد عن التوطين ونطاقات ونظام العمل",
    "site_quality": "ارتفاع إصابات العمل وعيوب البناء ومخالفات السلامة المهنية وسقالات الموقع",
    "saudi_economy": "نمو الاقتصاد السعودي ضمن رؤية 2030 وصندوق الاستثمارات والمشاريع الكبرى",
    "saudi_trends": "وسم يتصدر الأكثر تداولاً والأكثر بحثاً وحديث السوشيال في السعودية",
    "real_estate": "ارتفاع أسعار الأراضي وتمويل عقاري وتطوير عقاري وطلب على المساكن",
    "occasions": "احتفالات اليوم الوطني ويوم التأسيس ويوم العلم وموسم الرياض",
    "business_leadership": "قيادة الشركات وثقافة العمل والتوظيف والإنتاجية وريادة أعمال",
}


def test_samples_cover_every_configured_pillar():
    assert set(SAMPLES) == set(_persona_yaml()["content_pillars"])


@pytest.mark.parametrize("pillar", sorted(SAMPLES))
def test_classifier_can_assign_every_configured_pillar(pillar):
    ranked = pillars_ranked(_article(SAMPLES[pillar]))
    assert ranked[0] == pillar, f"{pillar!r} sample classified as {ranked[:3]}"


# ── integration: a draft can be created and saved for EVERY configured pillar ──

@pytest.mark.parametrize("pillar", sorted(_persona_yaml()["content_pillars"]))
def test_draft_can_be_saved_for_every_configured_pillar(db_session, pillar):
    _seed_real_persona(db_session)
    post = PostRepository(db_session).create_draft(
        platform="x", language="ar", pillar=pillar, content_type="news_insight", hook="h", body="b",
        approval_level="green", review_notes=None, fact_confidence=0.9, relevance=50.0)
    db_session.flush()
    db_session.refresh(post)
    assert post.pillar == pillar


def test_every_pillar_the_classifier_emits_can_be_saved_on_a_fresh_database(db_session):
    """The exact failure that existed: classifier emitted keys the seeded pillars table lacked."""
    _seed_real_persona(db_session)
    for key in PILLAR_TERMS:
        nested = db_session.begin_nested()
        PostRepository(db_session).create_draft(
            platform="x", language="ar", pillar=key, content_type="news_insight", hook="h", body="b",
            approval_level="green", review_notes=None, fact_confidence=0.9, relevance=50.0)
        nested.commit()


def test_scored_articles_and_trends_can_be_saved_for_every_configured_pillar(db_session):
    _seed_real_persona(db_session)
    articles, trends = RawArticleRepository(db_session), TrendRepository(db_session)
    for i, key in enumerate(PILLAR_TERMS):
        art = _article(f"article {i}")
        art.url = f"https://example.com/{i}"
        art.scores = {"total": 50.0}
        art.meta = {"pillar": key}
        row = articles.save_scored(art, source_id=None)
        assert row.pillar == key
        assert trends.create(pillar=key, headline="t", article_ids=[], strength=0.5).pillar == key
    db_session.flush()


# ── resilience: code deployed before the persona is re-seeded must not crash ──

def test_unknown_pillar_degrades_to_no_pillar_instead_of_failing(db_session):
    repo = PersonaRepository(db_session)
    repo.upsert_pillar(key="ai_technology", label_ar="x", label_en="x", target_share=1.0)
    db_session.flush()

    assert repo.resolve_pillar("ai_technology") == "ai_technology"
    assert repo.resolve_pillar("not_seeded_yet") is None
    assert repo.resolve_pillar(None) is None

    art = _article("unseeded")
    art.scores, art.meta = {"total": 10.0}, {"pillar": "not_seeded_yet"}
    row = RawArticleRepository(db_session).save_scored(art, source_id=None)   # must not raise an FK error
    assert row.pillar is None
    assert TrendRepository(db_session).create(pillar="not_seeded_yet", headline="t", article_ids=[],
                                              strength=0.1).pillar is None
    db_session.flush()


# ── production safety: pillars from an older persona are hidden, never modified or deleted ──

LEGACY = {"investment": 0.05, "entrepreneurship": 0.11, "construction_engineering": 0.15}


def test_legacy_pillars_and_their_posts_are_left_untouched(db_session):
    repo = PersonaRepository(db_session)
    for key, share in LEGACY.items():                       # what production holds today
        repo.upsert_pillar(key=key, label_ar=key, label_en=key, target_share=share)
    db_session.flush()
    old_post = PostRepository(db_session).create_draft(
        platform="x", language="en", pillar="investment", content_type="news_insight", hook="old",
        body="an existing production post", approval_level="green", review_notes=None,
        fact_confidence=0.9, relevance=10.0)
    db_session.flush()

    seed_script.seed_persona(repo, _persona_yaml())         # deploy: the new persona is seeded
    db_session.flush()
    db_session.expire_all()

    active = {p.key for p in repo.list_pillars()}
    assert active == set(_persona_yaml()["content_pillars"])           # legacy hidden from live logic
    assert sum(float(p.target_share) for p in repo.list_pillars()) == pytest.approx(1.0)  # no 200%
    assert set(LEGACY) <= {p.key for p in repo.list_pillars(include_legacy=True)}

    for key, share in LEGACY.items():                       # rows untouched
        assert float(db_session.get(Pillar, key).target_share) == share
    survivor = db_session.get(Post, old_post.id)            # post untouched, still references its pillar
    assert survivor.pillar == "investment" and survivor.body == "an existing production post"
