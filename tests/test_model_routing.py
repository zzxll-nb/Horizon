"""Tests for cost-bounded final-item model routing."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from rich.console import Console

from src.ai.router import route_deep_analysis
from src.ai.reviewer import ContentReviewer
from src.models import (
    AIConfig,
    ClassificationResult,
    CollectionConfig,
    ContentAnalysis,
    ContentItem,
    DeepAnalysisConfig,
    DigestConfig,
    ProcessingConfig,
    ProcessingResult,
    ProfileSettingsConfig,
    ReviewConfig,
    SourceType,
    ValueReview,
)
from src.orchestrator import HorizonOrchestrator


def make_item(item_id: str, score: float, category: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=item_id,
        url=f"https://example.com/{item_id}",
        published_at=datetime.now(timezone.utc),
        metadata={"category": category},
        profile="finance-news",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="finance-news", method="source_override"
            ),
            analysis=ContentAnalysis(score=score, reason="test", summary=item_id),
        ),
    )


def make_orchestrator(digest: DigestConfig) -> HorizonOrchestrator:
    orchestrator = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orchestrator.config = SimpleNamespace(
        ai=AIConfig(
            provider="openai",
            model="gpt-4.1-mini",
            api_key_env="OPENAI_API_KEY",
            review=ReviewConfig(enabled=True),
        ),
        digest=digest,
        collection=CollectionConfig(),
        processing=ProcessingConfig(
            profile_settings={
                "finance-news": ProfileSettingsConfig(threshold=7.0)
            }
        ),
    )
    orchestrator.console = Console(record=True)
    return orchestrator


def test_normal_high_value_item_routes_to_terra() -> None:
    item = make_item("ordinary-company-update", 7.6, "finance")

    result = route_deep_analysis([item], DeepAnalysisConfig(enabled=True))

    assert [entry.item.id for entry in result.terra] == [item.id]
    assert result.terra[0].reasoning_effort == "medium"
    assert result.sol == []


def test_score_at_sol_threshold_routes_to_sol() -> None:
    item = make_item("major-event", 8.5, "finance")

    result = route_deep_analysis([item], DeepAnalysisConfig(enabled=True))

    assert [entry.item.id for entry in result.sol] == [item.id]
    assert result.sol[0].reasoning_effort == "medium"


def test_critical_macro_event_forces_sol_with_high_reasoning() -> None:
    item = make_item("fed-decision", 7.8, "finance")
    item.title = "Federal Reserve announces an unexpected policy decision"

    result = route_deep_analysis([item], DeepAnalysisConfig(enabled=True))

    assert [entry.item.id for entry in result.sol] == [item.id]
    assert result.sol[0].critical is True
    assert result.sol[0].reasoning_effort == "high"


def test_sol_cap_falls_remaining_candidates_back_to_terra() -> None:
    items = [
        make_item("top", 9.8, "finance"),
        make_item("second", 9.2, "finance"),
        make_item("overflow", 8.9, "finance"),
    ]
    config = DeepAnalysisConfig(enabled=True, sol_max_items=1)

    result = route_deep_analysis(items, config)

    assert [entry.item.id for entry in result.sol] == ["top"]
    assert [entry.item.id for entry in result.terra] == ["second", "overflow"]


def test_two_extreme_systemic_events_allow_second_sol_slot() -> None:
    items = [make_item("first", 9.5, "finance"), make_item("second", 9.2, "finance")]
    for item in items:
        item.processing.review = ValueReview(
            mini_score=8.0,
            score=item.processing.analysis.score,
            decision="select",
            reason="systemic event",
            systemic_risk=True,
            critical_event=True,
            complexity="high",
        )

    result = route_deep_analysis(items, DeepAnalysisConfig(enabled=True))

    assert [entry.item.id for entry in result.sol] == ["first", "second"]


def test_filtered_item_never_reaches_deep_model_routing() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    items = [
        make_item("selected", 7.2, "finance"),
        make_item("filtered", 6.9, "finance"),
    ]

    filtered = asyncio.run(
        orchestrator.filter_items(items, topic_dedup=False, apply_balance=False)
    )
    routed = route_deep_analysis(
        filtered.items, DeepAnalysisConfig(enabled=True)
    )

    assert [entry.item.id for entry in routed.routed] == ["selected"]
    assert "filtered" not in [entry.item.id for entry in routed.routed]


def test_router_defensively_skips_below_threshold_item() -> None:
    item = make_item("below-threshold", 6.9, "finance")

    result = route_deep_analysis([item], DeepAnalysisConfig(enabled=True))

    assert result.routed == []
    assert [skipped.id for skipped in result.skipped] == [item.id]


def test_per_run_budget_skips_items_beyond_six() -> None:
    scores = [10.0, 9.8, 9.6, 9.4, 9.2, 9.0, 8.8]
    items = [
        make_item(f"item-{index}", score, "finance")
        for index, score in enumerate(scores)
    ]

    result = route_deep_analysis(
        items, DeepAnalysisConfig(enabled=True, max_items_per_run=6)
    )

    assert len(result.routed) == 6
    assert [item.id for item in result.skipped] == ["item-6"]


def test_old_ai_config_uses_safe_legacy_defaults() -> None:
    config = AIConfig(
        provider="openai", model="gpt-4.1-mini", api_key_env="OPENAI_API_KEY"
    )

    assert config.scoring_model is None
    assert config.screening_model is None
    assert config.review.enabled is False
    assert config.deep_analysis.enabled is False
    assert config.deep_analysis.minimum_score == 7.0
    assert config.deep_analysis.sol_threshold == 8.5
    assert config.deep_analysis.sol_max_items == 1


def test_deep_analysis_config_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValidationError, match="sol_threshold"):
        DeepAnalysisConfig(minimum_score=9.0, sol_threshold=8.5)


def test_mini_rejects_only_explicit_low_score_noise() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    item = make_item("celebrity-gossip", 4.0, "finance")
    item.processing.analysis.relevance = "irrelevant"
    item.processing.analysis.obvious_noise = True

    assert orchestrator.mini_screen_skip_reason(item) == "explicit_obvious_noise"


def test_mid_score_item_must_reach_terra_review() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    item = make_item("possible-market-impact", 6.2, "finance")

    assert orchestrator.mini_screen_skip_reason(item) is None


def test_protected_macro_event_survives_low_mini_score() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    item = make_item("fed-event", 3.5, "finance")
    item.title = "Federal Reserve changes liquidity facility terms"
    item.processing.analysis.relevance = "irrelevant"
    item.processing.analysis.obvious_noise = True

    assert orchestrator.is_review_protected(item)
    assert orchestrator.mini_screen_skip_reason(item) is None


def test_high_priority_mini_item_still_reaches_review() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    item = make_item("high-priority", 8.0, "finance")

    assert orchestrator.mini_screen_skip_reason(item) is None


def test_terra_review_can_upgrade_hidden_value() -> None:
    item = make_item("hidden-value", 6.0, "finance")

    class FakeClient:
        async def complete(self, system, user, temperature=None, max_tokens=None):
            return (
                '{"reviews":[{"id":"hidden-value","score":8.2,'
                '"decision":"select","reason":"second-order impact",'
                '"hidden_importance":true,"second_order_impact":true,'
                '"cross_asset_impact":false,"systemic_risk":false,'
                '"critical_event":false,"complexity":"medium"}]}'
            )

    result = asyncio.run(ContentReviewer(FakeClient()).review_batch([item]))

    assert result.reviewed_ids == [item.id]
    assert item.processing.review.mini_score == 6.0
    assert item.processing.review.score == 8.2
    assert item.processing.analysis.score == 8.2


def test_final_terra_selection_never_exceeds_six() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    items = [make_item(f"item-{index}", 9.0 - index / 10, "finance") for index in range(7)]
    for item in items:
        item.processing.review = ValueReview(
            mini_score=item.processing.analysis.score,
            score=item.processing.analysis.score,
            decision="select",
            reason="material",
        )

    selected = orchestrator.select_reviewed_items(items)

    assert len(selected) == 6


def test_freshness_gate_prioritizes_new_items_and_limits_background() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    orchestrator.config.collection = CollectionConfig(
        freshness_gate_enabled=True,
        max_background_items=1,
        background_min_score=8.0,
    )
    now = datetime.now(timezone.utc)
    fresh = make_item("fresh-market-news", 7.6, "markets")
    fresh.published_at = now - timedelta(hours=1)
    stale = make_item("stale-breaking-news", 9.8, "markets")
    stale.published_at = now - timedelta(days=90)
    background = make_item("annual-market-outlook", 9.2, "markets")
    background.title = "Annual Market Outlook research report"
    background.published_at = now - timedelta(days=90)
    second_background = make_item("industry-report", 9.0, "markets")
    second_background.title = "Semiconductor industry report"
    second_background.published_at = now - timedelta(days=60)
    for item in (fresh, stale, background, second_background):
        item.processing.review = ValueReview(
            mini_score=item.processing.analysis.score,
            score=item.processing.analysis.score,
            decision="select",
            reason="material",
        )

    selected = orchestrator.select_reviewed_items(
        [stale, background, second_background, fresh],
        freshness_cutoff=now - timedelta(hours=9),
    )

    assert [item.id for item in selected] == [fresh.id, background.id]


def test_freshness_gate_does_not_fill_quota_with_stale_news() -> None:
    orchestrator = make_orchestrator(DigestConfig())
    orchestrator.config.collection = CollectionConfig(
        freshness_gate_enabled=True,
        max_background_items=1,
    )
    now = datetime.now(timezone.utc)
    stale = make_item("old-news", 9.9, "markets")
    stale.published_at = now - timedelta(days=30)
    stale.processing.review = ValueReview(
        mini_score=9.9,
        score=9.9,
        decision="select",
        reason="material but old",
    )

    selected = orchestrator.select_reviewed_items(
        [stale],
        freshness_cutoff=now - timedelta(hours=15),
    )

    assert selected == []
