import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator, FormatChecker

from src.market_data import (
    MARKET_ASSETS,
    MarketAsset,
    MarketDataService,
    YahooFinanceProvider,
)
from src.storage.manager import StorageManager


class FixtureProvider:
    name = "fixture"

    def __init__(self, failures: set[str] | None = None):
        self.failures = failures or set()
        self.calls = 0

    async def fetch(self, asset, client):
        self.calls += 1
        if asset.id in self.failures:
            raise RuntimeError("fixture provider failure")
        index = next(i for i, item in enumerate(MARKET_ASSETS) if item.id == asset.id)
        change = (1.5, -1.5, 0.0)[index % 3]
        return MarketAsset(
            id=asset.id,
            name=asset.name,
            symbol=asset.symbol,
            current_value=100 + index,
            change=change,
            change_percent=change,
            updated_at="2026-01-15T12:00:00Z",
            data_status="live",
        )


def run(coroutine):
    return asyncio.run(coroutine)


def test_yahoo_adapter_maps_quote_and_zero_change():
    async def scenario():
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "chart": {
                        "result": [{
                            "meta": {
                                "regularMarketPrice": 100.0,
                                "regularMarketPreviousClose": 100.0,
                                "regularMarketChange": 0.0,
                                "regularMarketChangePercent": 0.0,
                                "regularMarketTime": 1768478400,
                            },
                            "timestamp": [1768478400],
                            "indicators": {"quote": [{"close": [100.0]}]},
                        }]
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await YahooFinanceProvider().fetch(MARKET_ASSETS[0], client)

    asset = run(scenario())
    assert asset.id == "sp500"
    assert asset.current_value == 100.0
    assert asset.change == 0.0
    assert asset.change_percent == 0.0
    assert asset.data_status == "live"


def test_service_maps_all_assets_writes_schema_valid_snapshot_and_uses_cache(tmp_path: Path):
    provider = FixtureProvider()
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    service = MarketDataService(StorageManager(data_dir=tmp_path), provider=provider, now=lambda: now)

    snapshot = run(service.refresh())
    cached = run(service.refresh())

    assert [asset.id for asset in snapshot.assets] == [asset.id for asset in MARKET_ASSETS]
    assert snapshot.data_status == "live"
    assert any(asset.change_percent and asset.change_percent > 0 for asset in snapshot.assets)
    assert any(asset.change_percent and asset.change_percent < 0 for asset in snapshot.assets)
    assert any(asset.change_percent == 0 for asset in snapshot.assets)
    assert provider.calls == len(MARKET_ASSETS)
    assert cached == snapshot

    schema = json.loads(Path("data/market-snapshot.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(snapshot.model_dump(mode="json"))
    written = json.loads((tmp_path / "market" / "latest.json").read_text(encoding="utf-8"))
    assert written["assets"][0]["id"] == "sp500"


def test_single_asset_failure_keeps_partial_snapshot(tmp_path: Path):
    service = MarketDataService(
        StorageManager(data_dir=tmp_path),
        provider=FixtureProvider({"gold"}),
        now=lambda: datetime(2026, 1, 15, tzinfo=timezone.utc),
    )

    snapshot = run(service.refresh())

    gold = next(asset for asset in snapshot.assets if asset.id == "gold")
    assert snapshot.data_status == "partial"
    assert gold.data_status == "unavailable"
    assert gold.current_value is None


def test_provider_failure_marks_all_assets_unavailable(tmp_path: Path):
    service = MarketDataService(
        StorageManager(data_dir=tmp_path),
        provider=FixtureProvider({asset.id for asset in MARKET_ASSETS}),
        now=lambda: datetime(2026, 1, 15, tzinfo=timezone.utc),
    )

    snapshot = run(service.refresh())

    assert snapshot.data_status == "unavailable"
    assert all(asset.data_status == "unavailable" for asset in snapshot.assets)


def test_failed_refresh_reuses_previous_data_as_stale(tmp_path: Path):
    current_time = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    storage = StorageManager(data_dir=tmp_path)
    service = MarketDataService(storage, provider=FixtureProvider(), now=lambda: current_time)
    run(service.refresh())

    current_time += timedelta(minutes=16)
    service.provider = FixtureProvider({asset.id for asset in MARKET_ASSETS})
    snapshot = run(service.refresh(force=True))

    assert snapshot.data_status == "stale"
    assert all(asset.data_status == "stale" for asset in snapshot.assets)
    assert all(asset.current_value is not None for asset in snapshot.assets)
