from datetime import datetime, timedelta, timezone

from src.models import ContentItem, SourceType
from src.processing.event_clusters import cap_ai_candidates, cluster_events


NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)


def item(item_id: str, title: str, tier: int, hours: int = 0) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=title,
        url=f"https://example.com/{item_id}",
        content="facts " * (4 - tier),
        published_at=NOW - timedelta(hours=hours),
        metadata={"source_name": f"Tier {tier}", "source_tier": tier},
        profile="markets-news",
    )


def test_same_event_clusters_and_prefers_tier_one() -> None:
    result = cluster_events(
        [
            item("media", "Fed cuts rates as inflation cools - CNBC", 2),
            item("official", "Fed cuts rates as inflation cools", 1, 1),
            item("other", "Oil rises after inventory report", 2),
        ]
    )

    assert len(result.items) == 2
    event = next(value for value in result.items if value.metadata["source_count"] == 2)
    assert event.id == "official"
    assert event.metadata["alternate_sources"][0]["item_id"] == "media"
    assert result.clustered_count == 1


def test_candidate_cap_prefers_quality_then_corroboration() -> None:
    tier_one = item("official", "Official release", 1)
    corroborated = item("many", "Widely covered earnings", 2)
    corroborated.metadata["source_count"] = 4
    weak = item("weak", "Aggregator item", 3)

    assert cap_ai_candidates([weak, corroborated, tier_one], 2) == [tier_one, corroborated]


def test_time_distance_prevents_false_cluster() -> None:
    result = cluster_events(
        [item("new", "Fed cuts rates as inflation cools", 1), item("old", "Fed cuts rates as inflation cools", 1, 48)]
    )
    assert len(result.items) == 2
