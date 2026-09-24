"""Tests for cost-bounded final-item model routing."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from rich.console import Console

from src.ai.router import route_deep_analysis
from src.models import (
    AIConfig,
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    DeepAnalysisConfig,
    DigestConfig,
    ProcessingConfig,
    ProcessingResult,
    ProfileSettingsConfig,
    SourceType,
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
        digest=digest,
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
    config = DeepAnalysisConfig(enabled=True, sol_max_items=2)

    result = route_deep_analysis(items, config)

    assert [entry.item.id for entry in result.sol] == ["top", "second"]
    assert [entry.item.id for entry in result.terra] == ["overflow"]


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


def test_per_run_budget_skips_items_beyond_eight() -> None:
    scores = [10.0, 9.8, 9.6, 9.4, 9.2, 9.0, 8.8, 8.6, 8.4]
    items = [
        make_item(f"item-{index}", score, "finance")
        for index, score in enumerate(scores)
    ]

    result = route_deep_analysis(
        items, DeepAnalysisConfig(enabled=True, max_items_per_run=8)
    )

    assert len(result.routed) == 8
    assert [item.id for item in result.skipped] == ["item-8"]


def test_old_ai_config_uses_safe_legacy_defaults() -> None:
    config = AIConfig(
        provider="openai", model="gpt-4.1-mini", api_key_env="OPENAI_API_KEY"
    )

    assert config.scoring_model is None
    assert config.deep_analysis.enabled is False
    assert config.deep_analysis.minimum_score == 7.0
    assert config.deep_analysis.sol_threshold == 8.5
    assert config.deep_analysis.sol_max_items == 3


def test_deep_analysis_config_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValidationError, match="sol_threshold"):
        DeepAnalysisConfig(minimum_score=9.0, sol_threshold=8.5)
