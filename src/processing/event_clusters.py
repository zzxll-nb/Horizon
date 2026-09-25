"""Cheap, deterministic event clustering before any AI calls."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import timezone
from difflib import SequenceMatcher
from typing import Iterable

from ..models import ContentItem


_PUBLISHER_SUFFIX = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,45}$")
_TOKEN = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]{2,}")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for",
    "with", "from", "as", "at", "is", "are", "says", "said", "new",
    "latest", "update", "market", "markets", "news",
}


def source_tier(item: ContentItem) -> int:
    """Return the configured quality tier, defaulting unknown sources to Tier 3."""
    try:
        return max(1, min(3, int(item.metadata.get("source_tier", 3))))
    except (TypeError, ValueError):
        return 3


def source_name(item: ContentItem) -> str:
    for key in ("feed_name", "source_name", "watchlist", "domain"):
        if item.metadata.get(key):
            return str(item.metadata[key])
    return item.author or item.source_type.value


def normalize_title(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).casefold().strip()
    value = _PUBLISHER_SUFFIX.sub("", value)
    tokens = [token for token in _TOKEN.findall(value) if token not in _STOPWORDS]
    return " ".join(tokens)


def _tokens(item: ContentItem) -> set[str]:
    return set(normalize_title(item.title).split())


def _same_event(left: ContentItem, right: ContentItem) -> bool:
    hours = abs(
        (
            left.published_at.astimezone(timezone.utc)
            - right.published_at.astimezone(timezone.utc)
        ).total_seconds()
    ) / 3600
    if hours > 36:
        return False
    left_title = normalize_title(left.title)
    right_title = normalize_title(right.title)
    if not left_title or not right_title:
        return False
    if left_title == right_title:
        return True
    left_tokens, right_tokens = _tokens(left), _tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0
    lexical = SequenceMatcher(None, left_title, right_title).ratio()
    shared_entities = {
        token for token in left_tokens & right_tokens if len(token) >= 4 or token.isdigit()
    }
    return lexical >= 0.84 or (jaccard >= 0.62 and len(shared_entities) >= 2)


def _primary_key(item: ContentItem) -> tuple[int, int, float]:
    return (
        source_tier(item),
        -len(item.content or ""),
        -item.published_at.timestamp(),
    )


def _cluster_id(items: Iterable[ContentItem]) -> str:
    titles = sorted(normalize_title(item.title) for item in items)
    return "event:" + hashlib.sha256("\n".join(titles).encode()).hexdigest()[:20]


@dataclass
class EventClusterResult:
    items: list[ContentItem]
    clustered_count: int


def cluster_events(items: list[ContentItem]) -> EventClusterResult:
    """Merge obvious same-event coverage, preferring Tier 1 over Tier 2/3."""
    clusters: list[list[ContentItem]] = []
    for item in sorted(items, key=lambda value: value.published_at, reverse=True):
        target = next(
            (cluster for cluster in clusters if any(_same_event(item, other) for other in cluster)),
            None,
        )
        if target is None:
            clusters.append([item])
        else:
            target.append(item)

    results: list[ContentItem] = []
    for members in clusters:
        ordered = sorted(members, key=_primary_key)
        primary = ordered[0].model_copy(deep=True)
        alternates = list(primary.metadata.get("alternate_sources", []))
        for member in ordered[1:]:
            alternates.append(
                {
                    "name": source_name(member),
                    "url": str(member.url),
                    "published_at": member.published_at.isoformat(),
                    "tier": source_tier(member),
                    "title": member.title,
                    "snippet": (member.content or "")[:500],
                    "item_id": member.id,
                }
            )
            alternates.extend(member.metadata.get("alternate_sources", []))
        deduplicated_alternates = []
        seen_sources = {(source_name(primary), str(primary.url))}
        for alternate in alternates:
            alternate_url = str(alternate.get("url") or "")
            source_key = (str(alternate.get("name") or "Unknown"), alternate_url)
            if not alternate_url or source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            deduplicated_alternates.append(alternate)
        alternates = sorted(
            deduplicated_alternates,
            key=lambda entry: (int(entry.get("tier", 3)), str(entry.get("name", ""))),
        )
        event_id = _cluster_id(members)
        total_sources = 1 + len(alternates)
        primary.metadata.update(
            {
                "event_cluster_id": event_id,
                "event_member_ids": sorted(member.id for member in members),
                "event_fingerprint": event_id,
                "source_count": total_sources,
                "source_tiers": [source_tier(primary)]
                + [int(entry.get("tier", 3)) for entry in alternates],
                "alternate_sources": alternates,
                "corroborating_urls": [entry["url"] for entry in alternates],
                "corroborating_snippets": [
                    entry["snippet"] for entry in alternates[:3] if entry["snippet"]
                ],
                "clustered_count": total_sources - 1,
                "source_tier": source_tier(primary),
            }
        )
        results.append(primary)
    return EventClusterResult(
        items=results,
        clustered_count=max(0, len(items) - len(results)),
    )


def cap_ai_candidates(items: list[ContentItem], limit: int) -> list[ContentItem]:
    """Bound cheap-AI work using source quality, corroboration, and freshness."""
    return sorted(
        items,
        key=lambda item: (
            source_tier(item),
            -int(item.metadata.get("source_count", 1)),
            -item.published_at.timestamp(),
        ),
    )[:limit]
