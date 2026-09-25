"""Tests for reuse of unchanged long-form analysis."""

from datetime import datetime, timezone

from src.ai.analysis_cache import apply_cached_analysis, update_analysis_cache
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)


def make_item(content: str = "unchanged facts") -> ContentItem:
    return ContentItem(
        id="rss:test:stable",
        source_type=SourceType.RSS,
        title="Stable financial event",
        url="https://example.com/stable",
        content=content,
        published_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        profile="finance-news",
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="finance-news", method="source_override"
            ),
            analysis=ContentAnalysis(
                score=8.0, reason="material", summary="summary"
            ),
        ),
    )


def attach_artifact(item: ContentItem) -> None:
    item.processing.artifacts["zh"] = ContentArtifact(
        language="zh",
        title="稳定财经事件",
        blocks=[
            ContentBlock(id="summary", title="摘要", content="简短摘要"),
            ContentBlock(id="impact", title="重要性", content="影响市场预期"),
            ContentBlock(id="analysis", title="深度分析", content="分析" * 700),
            ContentBlock(
                id="watch_factors", title="观察指标", content="- 利率\n- 利润率"
            ),
            ContentBlock(
                id="related_assets", title="相关资产", content="- SPY\n- 美债"
            ),
        ],
    )


def test_unchanged_item_reuses_long_analysis() -> None:
    original = make_item()
    attach_artifact(original)
    cache = update_analysis_cache({}, [original])
    next_run = make_item()

    reused = apply_cached_analysis(next_run, cache)

    assert reused is True
    assert next_run.processing.artifacts["zh"].title == "稳定财经事件"


def test_substantive_content_change_invalidates_cache() -> None:
    original = make_item()
    attach_artifact(original)
    cache = update_analysis_cache({}, [original])
    changed = make_item("updated earnings guidance")

    assert apply_cached_analysis(changed, cache) is False
    assert changed.processing.artifacts == {}


def test_incompatible_cache_schema_is_not_reused() -> None:
    original = make_item()
    attach_artifact(original)
    cache = update_analysis_cache({}, [original])
    cache["schema_version"] = "0.9"

    assert apply_cached_analysis(make_item(), cache) is False


def test_alternate_source_order_does_not_invalidate_cache() -> None:
    original = make_item()
    original.metadata["alternate_sources"] = [
        {"name": "Reuters", "url": "https://r.example/item"},
        {"name": "CNBC", "url": "https://c.example/item"},
    ]
    original.metadata["source_count"] = 3
    attach_artifact(original)
    cache = update_analysis_cache({}, [original])
    next_run = make_item()
    next_run.metadata["alternate_sources"] = list(
        reversed(original.metadata["alternate_sources"])
    )
    next_run.metadata["source_count"] = 3

    assert apply_cached_analysis(next_run, cache) is True
