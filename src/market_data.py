"""Fetch, normalize, and cache the small market snapshot used by Dashboard."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal, Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from .storage.manager import StorageManager

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


@dataclass(frozen=True)
class MarketAssetDefinition:
    id: str
    name: str
    symbol: str


MARKET_ASSETS: tuple[MarketAssetDefinition, ...] = (
    MarketAssetDefinition("sp500", "S&P 500", "^GSPC"),
    MarketAssetDefinition("nasdaq_composite", "NASDAQ Composite", "^IXIC"),
    MarketAssetDefinition("dow_jones", "Dow Jones", "^DJI"),
    MarketAssetDefinition("gold", "Gold", "GC=F"),
    MarketAssetDefinition("wti", "WTI Crude Oil", "CL=F"),
    MarketAssetDefinition("bitcoin", "Bitcoin", "BTC-USD"),
    MarketAssetDefinition("us10y", "US 10Y Treasury Yield", "^TNX"),
)


AssetStatus = Literal["live", "stale", "unavailable", "sample"]
SnapshotStatus = Literal["live", "partial", "stale", "unavailable", "sample"]


class MarketAsset(BaseModel):
    id: str
    name: str
    symbol: str
    current_value: float | None = None
    change: float | None = None
    change_percent: float | None = None
    updated_at: str | None = None
    data_status: AssetStatus


class MarketSnapshot(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    data_status: SnapshotStatus
    generated_at: str
    provider: str = "yahoo_finance"
    assets: list[MarketAsset] = Field(default_factory=list)


class MarketDataProvider(Protocol):
    name: str

    async def fetch(self, asset: MarketAssetDefinition, client: httpx.AsyncClient) -> MarketAsset:
        """Return a normalized quote or raise when the provider cannot return one."""


class YahooFinanceProvider:
    """Minimal adapter for Yahoo Finance's public chart endpoint.

    The adapter is deliberately isolated so a key-backed provider can replace it
    later without changing the snapshot or Dashboard contracts.
    """

    name = "yahoo_finance"
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    async def fetch(self, asset: MarketAssetDefinition, client: httpx.AsyncClient) -> MarketAsset:
        url = f"{self.base_url}/{quote(asset.symbol, safe='')}"
        response = await client.get(
            url,
            params={"range": "2d", "interval": "1d", "includePrePost": "false"},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("chart", {}).get("result", [None])[0]
        if not isinstance(result, dict):
            raise ValueError("Yahoo Finance did not return chart data")

        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        close_values = [_as_number(value) for value in closes]
        latest_close = next((value for value in reversed(close_values) if value is not None), None)
        value = _as_number(meta.get("regularMarketPrice")) or latest_close
        previous_close = _as_number(meta.get("regularMarketPreviousClose"))
        if previous_close is None:
            previous_close = _as_number(meta.get("chartPreviousClose"))
        if value is None or previous_close is None:
            raise ValueError("Yahoo Finance returned an incomplete quote")

        change = _as_number(meta.get("regularMarketChange"))
        if change is None:
            change = value - previous_close
        change_percent = _as_number(meta.get("regularMarketChangePercent"))
        if change_percent is None:
            change_percent = (change / previous_close * 100) if previous_close else 0.0

        market_time = _as_number(meta.get("regularMarketTime"))
        if market_time is None:
            timestamps = result.get("timestamp", [])
            market_time = _as_number(timestamps[-1]) if timestamps else None
        updated_at = _iso_utc(datetime.fromtimestamp(market_time, tz=timezone.utc)) if market_time else _iso_utc(_utc_now())

        return MarketAsset(
            id=asset.id,
            name=asset.name,
            symbol=asset.symbol,
            current_value=value,
            change=change,
            change_percent=change_percent,
            updated_at=updated_at,
            data_status="live",
        )


class MarketDataService:
    """Refresh a cached MarketSnapshot without coupling it to the news run."""

    def __init__(
        self,
        storage: StorageManager,
        provider: MarketDataProvider | None = None,
        cache_ttl: timedelta = timedelta(minutes=15),
        now: Callable[[], datetime] = _utc_now,
    ):
        self.storage = storage
        self.provider = provider or YahooFinanceProvider()
        self.cache_ttl = cache_ttl
        self.now = now

    async def refresh(self, force: bool = False) -> MarketSnapshot:
        previous = self.storage.load_market_snapshot()
        if not force and previous is not None and self._is_fresh(previous):
            return previous

        previous_assets = {asset.id: asset for asset in previous.assets} if previous else {}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "HorizonMarketSnapshot/1.0 (+https://github.com/Thysrael/Horizon)",
            },
        ) as client:
            results = await asyncio.gather(
                *(self._fetch_one(asset, client) for asset in MARKET_ASSETS),
            )

        assets = [
            result if isinstance(result, MarketAsset) else self._fallback_asset(asset, previous_assets.get(asset.id))
            for asset, result in zip(MARKET_ASSETS, results, strict=True)
        ]
        snapshot = MarketSnapshot(
            data_status=self._snapshot_status(assets),
            generated_at=_iso_utc(self.now()),
            provider=self.provider.name,
            assets=assets,
        )
        self.storage.save_market_snapshot(snapshot.model_dump(mode="json"))
        return snapshot

    async def _fetch_one(self, asset: MarketAssetDefinition, client: httpx.AsyncClient) -> MarketAsset | Exception:
        try:
            return await self.provider.fetch(asset, client)
        except Exception as error:  # A single quote must not block the snapshot.
            logger.warning("Market quote unavailable for %s: %s", asset.symbol, error)
            return error

    def _is_fresh(self, snapshot: MarketSnapshot) -> bool:
        try:
            generated_at = datetime.fromisoformat(snapshot.generated_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return self.now() - generated_at <= self.cache_ttl

    @staticmethod
    def _fallback_asset(asset: MarketAssetDefinition, previous: MarketAsset | None) -> MarketAsset:
        if previous is not None and previous.current_value is not None:
            return previous.model_copy(update={"data_status": "stale"})
        return MarketAsset(id=asset.id, name=asset.name, symbol=asset.symbol, data_status="unavailable")

    @staticmethod
    def _snapshot_status(assets: list[MarketAsset]) -> SnapshotStatus:
        live_count = sum(asset.data_status == "live" for asset in assets)
        stale_count = sum(asset.data_status == "stale" for asset in assets)
        if live_count == len(assets):
            return "live"
        if live_count:
            return "partial"
        if stale_count:
            return "stale"
        return "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Horizon Dashboard market data")
    parser.add_argument("-d", "--data-dir", default="data", metavar="PATH")
    parser.add_argument("--force", action="store_true", help="Bypass the 15-minute cache")
    args = parser.parse_args()

    snapshot = asyncio.run(MarketDataService(StorageManager(data_dir=args.data_dir)).refresh(force=args.force))
    print(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
