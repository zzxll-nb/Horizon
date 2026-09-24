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
    assert set(config.sources.gdelt.profile or []) == EXPECTED_PROFILES
    assert set(config.sources.google_news.profile or []) == EXPECTED_PROFILES

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
