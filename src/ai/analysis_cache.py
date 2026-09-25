"""Persistent cache for reusable long-form dashboard analysis artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..dashboard_export import SCHEMA_VERSION, dashboard_skip_reason
from ..models import ContentArtifact, ContentItem


CACHE_SCHEMA_VERSION = "1.0"
_VOLATILE_METADATA = {
    "bookmarks",
    "descendants",
    "favorite_count",
    "fetched_at",
    "merged_sources",
    "alternate_sources",
    "corroborating_snippets",
    "corroborating_urls",
    "clustered_count",
    "event_cluster_id",
    "event_member_ids",
    "event_fingerprint",
    "source_count",
    "source_tiers",
    "reply_count",
    "retweet_count",
    "score",
    "upvote_ratio",
    "views",
}


def content_fingerprint(item: ContentItem) -> str:
    """Hash substantive input while ignoring volatile engagement counters."""
    metadata = {
        key: value
        for key, value in item.metadata.items()
        if key not in _VOLATILE_METADATA
    }
    payload = {
        "title": item.title,
        "url": str(item.url),
        "content": item.content or "",
        "author": item.author,
        "published_at": item.published_at.isoformat(),
        "metadata": metadata,
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def apply_cached_analysis(item: ContentItem, cache: dict[str, Any]) -> bool:
    """Restore compatible artifacts when the underlying news item is unchanged."""
    if item.processing is None:
        return False
    entries = cache.get("items", {})
    candidate_ids = [item.id, *item.metadata.get("event_member_ids", [])]
    entry = next(
        (entries.get(candidate_id) for candidate_id in candidate_ids if entries.get(candidate_id)),
        None,
    )
    if not isinstance(entry, dict):
        return False
    if cache.get("schema_version") != CACHE_SCHEMA_VERSION:
        return False
    if entry.get("dashboard_schema_version") != SCHEMA_VERSION:
        return False
    if entry.get("profile") != item.processing.classification.profile:
        return False
    if entry.get("fingerprint") != content_fingerprint(item):
        return False
    raw_artifacts = entry.get("artifacts")
    if not isinstance(raw_artifacts, dict) or not raw_artifacts:
        return False
    try:
        artifacts = {
            language: ContentArtifact.model_validate(value)
            for language, value in raw_artifacts.items()
        }
    except (TypeError, ValueError):
        return False

    previous = item.processing.artifacts
    item.processing.artifacts = artifacts
    if dashboard_skip_reason(item) is not None:
        item.processing.artifacts = previous
        return False
    return True


def update_analysis_cache(
    cache: dict[str, Any], items: list[ContentItem], *, max_entries: int = 500
) -> dict[str, Any]:
    """Merge successfully enriched items into the bounded cache."""
    existing = cache.get("items", {}) if isinstance(cache, dict) else {}
    entries = dict(existing) if isinstance(existing, dict) else {}
    for item in items:
        if item.processing is None or dashboard_skip_reason(item) is not None:
            continue
        entries[item.id] = {
            "fingerprint": content_fingerprint(item),
            "profile": item.processing.classification.profile,
            "dashboard_schema_version": SCHEMA_VERSION,
            "artifacts": {
                language: artifact.model_dump(mode="json")
                for language, artifact in item.processing.artifacts.items()
            },
        }
        for alias in item.metadata.get("event_member_ids", []):
            entries[str(alias)] = entries[item.id]
    if len(entries) > max_entries:
        entries = dict(list(entries.items())[-max_entries:])
    return {"schema_version": CACHE_SCHEMA_VERSION, "items": entries}
