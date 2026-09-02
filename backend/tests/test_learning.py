"""Domain-level learning engine tests — mirrors the checks that mattered in
``automation/feedback.py`` (the CLI reference this was ported from)."""

from app.domain.learning import (approval_by_pillar, clamp, compute_weights,
                                 engagement_rate, performance_by_pillar)


def test_engagement_rate_weights_shares_and_comments_higher_than_likes():
    heavy_likes = {"impressions": 1000, "likes": 100, "comments": 0, "shares": 0}
    heavy_shares = {"impressions": 1000, "likes": 0, "comments": 0, "shares": 34}  # ~ same weighted total
    assert abs(engagement_rate(heavy_likes) - engagement_rate(heavy_shares)) < 0.01


def test_engagement_rate_zero_impressions_is_zero_not_error():
    assert engagement_rate({"impressions": 0, "likes": 100}) == 0.0


def test_performance_by_pillar_averages_across_posts():
    rows = [
        {"pillar": "ai_technology", "impressions": 1000, "likes": 100, "comments": 0, "shares": 0},
        {"pillar": "ai_technology", "impressions": 1000, "likes": 50, "comments": 0, "shares": 0},
        {"pillar": "investment", "impressions": 1000, "likes": 10, "comments": 0, "shares": 0},
    ]
    result = performance_by_pillar(rows)
    assert result["ai_technology"] == (0.1 + 0.05) / 2
    assert result["investment"] == 0.01


def test_approval_by_pillar_requires_minimum_samples():
    decisions = [{"pillar": "ai_technology", "decision": "approved"},
                {"pillar": "ai_technology", "decision": "rejected"}]  # only 2 samples, below MIN_SAMPLES=3
    assert approval_by_pillar(decisions) == {}


def test_approval_by_pillar_computes_ratio_once_enough_samples():
    decisions = [{"pillar": "ai_technology", "decision": "approved"}] * 3 + \
                [{"pillar": "ai_technology", "decision": "rejected"}]
    result = approval_by_pillar(decisions)
    assert result["ai_technology"] == 0.75


def test_clamp_enforces_bounds():
    assert clamp(5.0) == 1.4
    assert clamp(-5.0) == 0.7
    assert clamp(1.0) == 1.0


def test_compute_weights_neutral_when_no_data():
    weights, detail = compute_weights([], [], ["ai_technology", "investment"])
    assert weights == {"ai_technology": 1.0, "investment": 1.0}
    assert "not enough data" in detail["ai_technology"]["why"]


def test_compute_weights_rewards_above_average_pillar():
    metrics = (
        [{"pillar": "ai_technology", "impressions": 1000, "likes": 200, "comments": 50, "shares": 30}] * 3
        + [{"pillar": "investment", "impressions": 1000, "likes": 5, "comments": 0, "shares": 0}] * 3
    )
    weights, detail = compute_weights(metrics, [], ["ai_technology", "investment"])
    assert weights["ai_technology"] > weights["investment"]
    assert "average" in detail["ai_technology"]["why"]
