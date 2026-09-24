import json
from pathlib import Path

from src.processing import ProfileRegistry
from src.storage.manager import StorageManager


ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "data" / "config.china-example.json"
EXPECTED_PROFILES = {
    "markets-news",
    "finance-news",
    "investing-news",
    "macro-news",
    "tech-ai-news",
}

EXPECTED_RSS_SOURCES = {
    "Federal Reserve Press Releases",
    "Federal Reserve Monetary Policy",
    "BLS Latest Numbers",
    "SEC Press Releases",
    "EIA Today in Energy",
    "EIA Press Releases",
    "CNBC Finance",
    "New York Times Business",
    "MarketWatch MarketPulse",
    "NVIDIA Press Releases",
    "AMD Press Releases",
    "OpenAI Blog",
    "AWS What's New",
}


def test_production_config_uses_market_focused_profiles_and_sources() -> None:
    config = StorageManager(config_path=str(CONFIG_PATH)).load_config()
    registry = ProfileRegistry.load(
        ROOT / config.processing.profiles_dir,
        config.processing.default_profile,
    )
    registry.validate_source_references(config.sources.model_dump(mode="json"))

    assert set(config.processing.profile_settings) == EXPECTED_PROFILES
    assert set(config.digest.profile_order) == EXPECTED_PROFILES
    assert config.processing.default_profile == "markets-news"
    assert config.collection.freshness_gate_enabled is True
    assert config.collection.max_background_items == 1
    assert config.sources.gdelt.timespan is None
    assert set(config.sources.gdelt.profile or []) == EXPECTED_PROFILES
    assert set(config.sources.google_news.profile or []) == EXPECTED_PROFILES
    assert {source.name for source in config.sources.rss} == EXPECTED_RSS_SOURCES
    assert len({str(source.url) for source in config.sources.rss}) == len(config.sources.rss)
    assert all(source.enabled for source in config.sources.rss)

    source_text = json.dumps(config.sources.model_dump(mode="json"), ensure_ascii=False)
    for forbidden in (
        "中国政府网",
        "/nyt/US.xml",
        "/nyt/World.xml",
        "international relations",
        "美国 政治",
        "国际 冲突",
    ):
        assert forbidden not in source_text


def test_dashboard_profiles_exclude_geographic_news_buckets() -> None:
    registry = ProfileRegistry.load(ROOT / "profiles", "markets-news")

    assert EXPECTED_PROFILES <= registry.ids
    assert {"china-news", "us-news", "international-news"}.isdisjoint(registry.ids)
