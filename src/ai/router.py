"""Deterministic model routing for final-item deep analysis."""

from dataclasses import dataclass, field
from typing import Literal

from ..models import ContentItem, DeepAnalysisConfig, ReasoningEffort


AnalysisTier = Literal["terra", "sol"]


@dataclass(frozen=True)
class RoutedAnalysisItem:
    item: ContentItem
    tier: AnalysisTier
    reasoning_effort: ReasoningEffort
    critical: bool = False


@dataclass
class DeepAnalysisRoutingResult:
    routed: list[RoutedAnalysisItem] = field(default_factory=list)
    skipped: list[ContentItem] = field(default_factory=list)

    @property
    def selected_items(self) -> list[ContentItem]:
        return [entry.item for entry in self.routed]

    @property
    def terra(self) -> list[RoutedAnalysisItem]:
        return [entry for entry in self.routed if entry.tier == "terra"]

    @property
    def sol(self) -> list[RoutedAnalysisItem]:
        return [entry for entry in self.routed if entry.tier == "sol"]


def importance_score(item: ContentItem) -> float:
    if item.processing and item.processing.analysis:
        score = item.processing.analysis.score
        if score is not None:
            return score
    return -1.0


def is_critical_event(item: ContentItem, config: DeepAnalysisConfig) -> bool:
    analysis = item.processing.analysis if item.processing else None
    searchable = " ".join(
        part
        for part in (
            item.title,
            analysis.summary if analysis else "",
            " ".join(analysis.tags) if analysis else "",
        )
        if part
    ).casefold()
    return any(keyword.casefold() in searchable for keyword in config.critical_keywords)


def route_deep_analysis(
    items: list[ContentItem], config: DeepAnalysisConfig
) -> DeepAnalysisRoutingResult:
    """Route only already-selected items, enforcing per-run analysis budgets."""
    ranked = sorted(items, key=importance_score, reverse=True)
    eligible = [
        item for item in ranked if importance_score(item) >= config.minimum_score
    ]
    below_threshold = [
        item for item in ranked if importance_score(item) < config.minimum_score
    ]
    selected = eligible[: config.max_items_per_run]
    skipped = eligible[config.max_items_per_run :] + below_threshold

    critical_by_id = {
        item.id: is_critical_event(item, config)
        for item in selected
    }
    sol_candidates = [
        item
        for item in selected
        if importance_score(item) >= config.sol_threshold
        or critical_by_id[item.id]
    ]
    sol_ids = {
        item.id
        for item in sorted(sol_candidates, key=importance_score, reverse=True)[
            : config.sol_max_items
        ]
    }

    routed: list[RoutedAnalysisItem] = []
    for item in selected:
        critical = critical_by_id[item.id]
        if item.id in sol_ids:
            effort = (
                config.sol_high_reasoning_effort
                if critical and config.sol_high_reasoning_for_critical
                else config.sol_reasoning_effort
            )
            routed.append(
                RoutedAnalysisItem(item, "sol", effort, critical=critical)
            )
        else:
            routed.append(
                RoutedAnalysisItem(
                    item,
                    "terra",
                    config.terra_reasoning_effort,
                    critical=critical,
                )
            )

    return DeepAnalysisRoutingResult(routed=routed, skipped=skipped)
