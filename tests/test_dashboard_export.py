import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from src.dashboard_export import build_dashboard_snapshot, dashboard_skip_reason
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.storage.manager import StorageManager


NOW = datetime(2026, 1, 15, 8, 30, tzinfo=timezone.utc)
PROFILES = (
    "markets-news",
    "finance-news",
    "investing-news",
    "macro-news",
    "tech-ai-news",
)


def _item(profile: str, index: int, score: float) -> ContentItem:
    title = f"原始标题 {index}"
    title_cn = title if index == 4 else f"中文标题 {index}"
    blocks = [
        ContentBlock(
            id="summary",
            title="摘要",
            content=f"这是第 {index} 条新闻的中文摘要。",
            primary=True,
        ),
        ContentBlock(
            id="analysis",
            title="深度分析",
            content="研究" * 350,
        ),
        ContentBlock(
            id="watch_factors",
            title="后续观察指标",
            content="- 下一次财报\n- 资本开支",
        ),
        ContentBlock(
            id="related_assets",
            title="关联资产",
            content="- 示例指数：验证关联资产导出",
        ),
    ]
    if index != 4:
        blocks.append(
            ContentBlock(
                id="impact",
                title="为什么重要",
                content=f"这是第 {index} 条新闻的重要性说明。",
            )
        )
    metadata = {"feed_name": f"来源 {index}"}
    if index == 0:
        metadata["merged_sources"] = ["rss", "google_news"]
        metadata["updated_at"] = "2026-01-15T08:00:00Z"

    return ContentItem(
        id=f"rss:fixture:{index}",
        source_type=SourceType.RSS,
        title=title,
        url=f"https://example.com/news/{index}",
        published_at=NOW - timedelta(hours=index),
        metadata=metadata,
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile=profile,
                method="source_override",
            ),
            analysis=ContentAnalysis(
                score=score,
                reason="fixture",
                summary=f"分析摘要 {index}",
            ),
            artifacts={
                "zh": ContentArtifact(
                    language="zh",
                    title=title_cn,
                    blocks=blocks,
                )
            },
        ),
    )


def _snapshot() -> dict:
    scores = (9.1, 8.0, 7.9, 5.0, 4.9)
    return build_dashboard_snapshot(
        [_item(profile, index, scores[index]) for index, profile in enumerate(PROFILES)],
        period_start=NOW - timedelta(hours=24),
        period_end=NOW,
        generated_at=NOW,
        total_fetched=25,
    )


def test_snapshot_matches_json_schema_and_contract() -> None:
    snapshot = _snapshot()
    schema_path = Path(__file__).parents[1] / "data" / "dashboard-snapshot.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(snapshot)

    assert snapshot["data_status"] == "live"
    assert {item["category"] for item in snapshot["news"]} == {
        "markets",
        "finance",
        "investing",
        "macro",
        "tech_ai",
    }
    assert [item["importance"] for item in snapshot["news"]] == [
        {"score": 91, "level": "high"},
        {"score": 80, "level": "high"},
        {"score": 79, "level": "medium"},
        {"score": 50, "level": "medium"},
        {"score": 49, "level": "low"},
    ]
    assert snapshot["news"][0]["updated_at"] == "2026-01-15T08:00:00Z"
    assert len(snapshot["news"][0]["sources"]) == 2
    assert snapshot["news"][4]["title_original"] is None
    assert snapshot["news"][4]["why_important"] is None
    assert snapshot["news"][4]["updated_at"] is None
    assert len(snapshot["news"][0]["analysis"]) == 700
    assert snapshot["news"][0]["watch_factors"] == ["下一次财报", "资本开支"]
    assert snapshot["news"][0]["related_assets"] == [
        "示例指数：验证关联资产导出"
    ]
    assert {item["content_kind"] for item in snapshot["news"]} == {"news"}
    assert {event["id"] for event in snapshot["briefing"]["events"]} <= {
        item["id"] for item in snapshot["news"]
    }


def test_unmapped_profile_is_skipped_without_failing(caplog) -> None:
    snapshot = build_dashboard_snapshot(
        [_item("unknown-profile", 0, 9.0)],
        period_start=NOW - timedelta(hours=24),
        period_end=NOW,
        generated_at=NOW,
        total_fetched=1,
    )

    assert snapshot["news"] == []
    assert snapshot["briefing"]["events"] == []
    assert "unmapped profile" in caplog.text


def test_export_marks_pre_window_item_as_background_research() -> None:
    snapshot = build_dashboard_snapshot(
        [_item("markets-news", 2, 8.5)],
        period_start=NOW - timedelta(hours=1),
        period_end=NOW,
        generated_at=NOW,
        total_fetched=1,
    )

    assert snapshot["news"][0]["content_kind"] == "background_research"
    assert snapshot["briefing"]["events"][0]["content_kind"] == "background_research"


def test_dashboard_skip_reason_reports_unmapped_profile() -> None:
    item = _item("unknown-profile", 0, 9.0)

    assert dashboard_skip_reason(item) == "unmapped_profile:unknown-profile"


def test_storage_saves_latest_and_dated_archive(tmp_path) -> None:
    storage = StorageManager(data_dir=str(tmp_path / "data"))
    latest, archive = storage.save_dashboard_snapshot("2026-01-15", _snapshot())

    assert latest == tmp_path / "data" / "dashboard" / "latest.json"
    assert archive == tmp_path / "data" / "dashboard" / "2026-01-15.json"
    assert json.loads(latest.read_text(encoding="utf-8")) == json.loads(
        archive.read_text(encoding="utf-8")
    )


def test_example_contains_three_distinct_long_research_analyses() -> None:
    root = Path(__file__).parents[1]
    example = json.loads(
        (root / "data" / "dashboard-snapshot.example.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (root / "data" / "dashboard-snapshot.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)

    assert example["news"][0]["content_kind"] == "background_research"
    assert example["briefing"]["events"][0]["content_kind"] == "background_research"

    by_category = {item["category"]: item for item in example["news"]}
    samples = [
        by_category[key]["analysis"]
        for key in ("finance", "macro", "tech_ai")
    ]
    assert len(set(samples)) == 3
    for analysis in samples:
        chinese_chars = sum("\u3400" <= char <= "\u9fff" for char in analysis)
        assert chinese_chars >= 700
        assert len({part for part in analysis.split("。") if part.strip()}) >= 12
