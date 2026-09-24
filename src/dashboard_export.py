"""Build the stable JSON contract consumed by the dashboard."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import ContentBlock, ContentItem


logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"
CATEGORY_MAP = {
    "china-news": "china",
    "us-news": "us",
    "international-news": "international",
    "finance-news": "finance",
    "tech-ai-news": "tech_ai",
}
CATEGORIES = [
    {"id": "china", "display_name": "中国"},
    {"id": "us", "display_name": "美国"},
    {"id": "international", "display_name": "国际"},
    {"id": "finance", "display_name": "财经"},
    {"id": "tech_ai", "display_name": "科技 / AI"},
]


def dashboard_skip_reason(item: ContentItem) -> str | None:
    """Return the contract reason an item cannot be exported."""
    processing = item.processing
    if processing is None or processing.analysis is None:
        return "missing_analysis"
    if processing.classification.profile not in CATEGORY_MAP:
        return f"unmapped_profile:{processing.classification.profile}"
    if processing.analysis.score is None:
        return "missing_importance_score"
    return None


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_utc_iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return _utc_iso(parsed)
    return None


def _source_name(item: ContentItem) -> str:
    metadata = item.metadata
    for key in ("feed_name", "source_name", "watchlist", "domain", "repo"):
        if metadata.get(key):
            return str(metadata[key])
    if metadata.get("subreddit"):
        return f"r/{metadata['subreddit']}"
    if metadata.get("channel"):
        return f"@{metadata['channel']}"
    if metadata.get("gn_query"):
        return f"Google News: {metadata['gn_query']}"
    return item.author or item.source_type.value


def _block(blocks: Iterable[ContentBlock], block_id: str) -> ContentBlock | None:
    return next((block for block in blocks if block.id == block_id), None)


def _importance(score: float) -> dict[str, int | str]:
    normalized = max(0, min(100, round(score * 10)))
    level = "high" if normalized >= 80 else "medium" if normalized >= 50 else "low"
    return {"score": normalized, "level": level}


def _sources(item: ContentItem) -> list[dict[str, str | None]]:
    url = str(item.url)
    published_at = _utc_iso(item.published_at)
    primary_name = _source_name(item)
    sources = [{"name": primary_name, "url": url, "published_at": published_at}]

    # URL-level deduplication preserves source types in metadata. These entries
    # share the canonical URL by definition; no additional fetch is required.
    for source_type in item.metadata.get("merged_sources", []):
        source_name = str(source_type)
        if source_name in {item.source_type.value, primary_name}:
            continue
        sources.append({"name": source_name, "url": url, "published_at": published_at})
    return sources


def _news_event(item: ContentItem) -> dict[str, Any] | None:
    processing = item.processing
    if processing is None or processing.analysis is None:
        logger.warning("Skipping dashboard item %s without analysis", item.id)
        return None

    category = CATEGORY_MAP.get(processing.classification.profile)
    if category is None:
        logger.warning(
            "Skipping dashboard item %s with unmapped profile %s",
            item.id,
            processing.classification.profile,
        )
        return None

    score = processing.analysis.score
    if score is None:
        logger.warning("Skipping dashboard item %s without importance score", item.id)
        return None

    artifact = processing.artifacts.get("zh")
    if artifact is None:
        artifact = next(
            (value for key, value in processing.artifacts.items() if key.lower().startswith("zh")),
            None,
        )
    blocks = artifact.blocks if artifact else []
    summary_block = _block(blocks, "summary")
    impact_block = _block(blocks, "impact")
    title_cn = artifact.title if artifact and artifact.title.strip() else item.title
    summary = (
        summary_block.content
        if summary_block and summary_block.content.strip()
        else processing.analysis.summary or item.title
    )
    sources = _sources(item)
    primary_source = sources[0]["name"]
    updated_at = item.metadata.get("updated_at", item.metadata.get("modified_at"))

    return {
        "id": item.id,
        "title_cn": title_cn,
        "title_original": None if item.title == title_cn else item.title,
        "summary": summary,
        "why_important": (
            impact_block.content if impact_block and impact_block.content.strip() else None
        ),
        "category": category,
        "importance": _importance(score),
        "published_at": _utc_iso(item.published_at),
        "updated_at": _optional_utc_iso(updated_at),
        "sources": sources,
        "primary_source": primary_source,
        "primary_url": str(item.url),
    }


def build_dashboard_snapshot(
    items: Iterable[ContentItem],
    *,
    period_start: datetime,
    period_end: datetime,
    total_fetched: int,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert final enriched items without performing additional AI work."""
    generated_at = generated_at or datetime.now(timezone.utc)
    news = []
    for item in items:
        event = _news_event(item)
        if event is not None:
            news.append(event)

    briefing_events = [
        {
            "id": event["id"],
            "title_cn": event["title_cn"],
            "summary": event["summary"],
            "why_important": event["why_important"],
            "category": event["category"],
            "importance": event["importance"],
            "source_count": len(event["sources"]),
            "source_names": list(dict.fromkeys(source["name"] for source in event["sources"])),
            "published_at": event["published_at"],
        }
        for event in news[:8]
    ]
    category_names = [
        category["display_name"]
        for category in CATEGORIES
        if any(event["category"] == category["id"] for event in news)
    ]
    covered = "、".join(category_names) if category_names else "暂无分类"

    return {
        "schema_version": SCHEMA_VERSION,
        "data_status": "live",
        "generated_at": _utc_iso(generated_at),
        "period_start": _utc_iso(period_start),
        "period_end": _utc_iso(period_end),
        "briefing": {
            "title": "今日 AI Briefing",
            "summary": f"本期共抓取 {total_fetched} 条信息，筛选出 {len(news)} 条重要事件，覆盖{covered}。",
            "events": briefing_events,
        },
        "news": news,
        "categories": CATEGORIES,
        "market": None,
    }
