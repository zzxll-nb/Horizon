"""Small adapters for public U.S. macro and filing endpoints."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import httpx

from .base import BaseScraper
from ..models import (
    BLSConfig,
    ContentItem,
    SECFilingsConfig,
    SourceType,
    TreasuryConfig,
)


PUBLIC_HEADERS = {
    "User-Agent": "Horizon Market Intelligence public-data reader contact=opendata@sec.gov",
    "Accept": "application/json, application/rss+xml, text/html;q=0.8",
}


class BLSDataScraper(BaseScraper):
    """Detect changes in selected series through the official BLS public API.

    The caller persists ``updated_state``. On a first run the current values are
    baselined without being emitted as fresh news, which prevents old monthly
    observations from masquerading as a new release after deployment.
    """

    SOURCE_TYPE = SourceType.BLS

    def __init__(
        self,
        config: BLSConfig,
        http_client: httpx.AsyncClient,
        previous_state: dict[str, str] | None = None,
    ):
        super().__init__({"bls": config}, http_client)
        self.bls_config = config
        self.previous_state = previous_state or {}
        self.updated_state: dict[str, str] = dict(self.previous_state)
        self.source_health: dict[str, dict[str, object]] = {}

    async def fetch(self, since: datetime) -> list[ContentItem]:
        if not self.bls_config.enabled or not self.bls_config.series:
            return []
        series_map = {series.id: series for series in self.bls_config.series}
        payload = {"seriesid": list(series_map)}
        try:
            response = await self.client.post(
                str(self.bls_config.api_url),
                json=payload,
                headers=PUBLIC_HEADERS,
                follow_redirects=True,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("status") != "REQUEST_SUCCEEDED":
                raise ValueError(f"BLS API status={body.get('status')!r}")
            raw_series = body.get("Results", {}).get("series", [])
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            self.source_health["BLS Public Data API"] = {
                "status": "failure",
                "fetched_count": 0,
                "duplicate_count": 0,
                "http_status": status,
                "error": f"{type(exc).__name__}: {exc}",
            }
            return []

        now = datetime.now(timezone.utc)
        items: list[ContentItem] = []
        first_observation = not bool(self.previous_state)
        for series_result in raw_series:
            series_id = str(series_result.get("seriesID", ""))
            definition = series_map.get(series_id)
            data = series_result.get("data") or []
            if definition is None or not data:
                continue
            latest = next((row for row in data if row.get("latest") == "true"), data[0])
            period_key = (
                f"{latest.get('year')}:{latest.get('period')}:{latest.get('value')}"
            )
            previous_key = self.previous_state.get(series_id)
            self.updated_state[series_id] = period_key
            if first_observation or previous_key in {None, period_key}:
                continue
            previous_value = data[1].get("value") if len(data) > 1 else None
            period_name = latest.get("periodName") or latest.get("period")
            value = latest.get("value")
            unit = f" {definition.unit}" if definition.unit else ""
            comparison = (
                f"，前值 {previous_value}{unit}" if previous_value is not None else ""
            )
            title = f"BLS：{definition.name}更新至 {value}{unit}"
            content = (
                f"美国劳工统计局公开数据 API 更新了 {definition.name}。"
                f"报告期为 {latest.get('year')} 年 {period_name}，"
                f"最新值 {value}{unit}{comparison}。"
            )
            items.append(
                ContentItem(
                    id=self._generate_id("bls", "series", f"{series_id}:{period_key}"),
                    source_type=self.SOURCE_TYPE,
                    title=title,
                    url=str(self.bls_config.api_url),
                    content=content,
                    author="U.S. Bureau of Labor Statistics",
                    published_at=now,
                    profile=self.bls_config.profile,
                    metadata={
                        "source_name": "BLS Public Data API",
                        "source_tier": self.bls_config.tier,
                        "category": self.bls_config.category,
                        "series_id": series_id,
                        "release_key": period_key,
                    },
                )
            )
        self.source_health["BLS Public Data API"] = {
            "status": "success" if items else "empty",
            "fetched_count": len(items),
            "duplicate_count": 0,
            "http_status": response.status_code,
            "error": None,
        }
        return items


class TreasuryReleaseScraper(BaseScraper):
    """Read the Treasury's public JSON press-release manifest."""

    SOURCE_TYPE = SourceType.TREASURY

    def __init__(self, config: TreasuryConfig, http_client: httpx.AsyncClient):
        super().__init__({"treasury": config}, http_client)
        self.treasury_config = config
        self.source_health: dict[str, dict[str, object]] = {}

    async def fetch(self, since: datetime) -> list[ContentItem]:
        if not self.treasury_config.enabled:
            return []
        try:
            manifest_response = await self.client.get(
                str(self.treasury_config.manifest_url),
                headers=PUBLIC_HEADERS,
                follow_redirects=True,
            )
            manifest_response.raise_for_status()
            manifest = manifest_response.json()
            shards = manifest.get("searchShards") or []
            current_year = str(datetime.now(timezone.utc).year)
            shard_path = next(
                (entry.get("path") for entry in shards if entry.get("name") == current_year),
                None,
            )
            if not shard_path:
                raise ValueError("Treasury current-year release shard missing")
            shard_url = urljoin(str(self.treasury_config.index_url), shard_path)
            response = await self.client.get(
                shard_url, headers=PUBLIC_HEADERS, follow_redirects=True
            )
            response.raise_for_status()
            records = response.json().get("items") or []
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            self.source_health["U.S. Treasury Releases"] = {
                "status": "failure",
                "fetched_count": 0,
                "duplicate_count": 0,
                "http_status": status,
                "error": f"{type(exc).__name__}: {exc}",
            }
            return []

        since_utc = (
            since.replace(tzinfo=timezone.utc)
            if since.tzinfo is None
            else since.astimezone(timezone.utc)
        )
        keywords = [keyword.casefold() for keyword in self.treasury_config.keywords]
        items: list[ContentItem] = []
        for record in records:
            try:
                published = datetime.fromisoformat(
                    str(record["datetime"]).replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            title = str(record.get("title") or "").strip()
            if published < since_utc or not title:
                continue
            searchable = f"{title} {record.get('searchText', '')}".casefold()
            if keywords and not any(keyword in searchable for keyword in keywords):
                continue
            url = urljoin(str(self.treasury_config.index_url), str(record.get("url", "")))
            native_id = hashlib.sha256(url.encode()).hexdigest()[:16]
            items.append(
                ContentItem(
                    id=self._generate_id("treasury", "release", native_id),
                    source_type=self.SOURCE_TYPE,
                    title=title,
                    url=url,
                    content=title,
                    author="U.S. Department of the Treasury",
                    published_at=published,
                    profile=self.treasury_config.profile,
                    metadata={
                        "source_name": "U.S. Treasury Releases",
                        "source_tier": self.treasury_config.tier,
                        "category": self.treasury_config.category,
                    },
                )
            )
        self.source_health["U.S. Treasury Releases"] = {
            "status": "success" if items else "empty",
            "fetched_count": len(items),
            "duplicate_count": 0,
            "http_status": response.status_code,
            "error": None,
        }
        return items


class SECFilingsScraper(BaseScraper):
    """Fetch material forms for a small configured EDGAR company universe."""

    SOURCE_TYPE = SourceType.SEC_FILINGS
    BASE_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(self, config: SECFilingsConfig, http_client: httpx.AsyncClient):
        super().__init__({"sec_filings": config}, http_client)
        self.sec_config = config
        self.source_health: dict[str, dict[str, object]] = {}

    async def fetch(self, since: datetime) -> list[ContentItem]:
        if not self.sec_config.enabled:
            return []
        batches = await asyncio.gather(
            *(self._fetch_company(company, since) for company in self.sec_config.companies),
            return_exceptions=True,
        )
        items: list[ContentItem] = []
        failures = 0
        for batch in batches:
            if isinstance(batch, Exception):
                failures += 1
            else:
                items.extend(batch)
        if failures == len(batches) and batches:
            status = "failure"
        elif failures:
            status = "degraded"
        else:
            status = "success" if items else "empty"
        self.source_health["SEC EDGAR Watch Universe"] = {
            "status": status,
            "fetched_count": len(items),
            "duplicate_count": 0,
            "http_status": None,
            "error": f"{failures} company request(s) failed" if failures else None,
        }
        return items

    async def _fetch_company(self, company: Any, since: datetime) -> list[ContentItem]:
        cik = str(company.cik).zfill(10)
        response = await self.client.get(
            self.BASE_URL.format(cik=cik),
            headers=PUBLIC_HEADERS,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form") or []
        since_utc = (
            since.replace(tzinfo=timezone.utc)
            if since.tzinfo is None
            else since.astimezone(timezone.utc)
        )
        results: list[ContentItem] = []
        for index, form in enumerate(forms):
            if form not in self.sec_config.forms:
                continue
            try:
                acceptance_values = recent.get("acceptanceDateTime") or []
                acceptance = (
                    acceptance_values[index] if index < len(acceptance_values) else None
                )
                if acceptance:
                    filed = datetime.fromisoformat(str(acceptance).replace("Z", "+00:00"))
                    if filed.tzinfo is None:
                        filed = filed.replace(tzinfo=timezone.utc)
                    filed = filed.astimezone(timezone.utc)
                else:
                    filed = datetime.fromisoformat(
                        str(recent["filingDate"][index])
                    ).replace(tzinfo=timezone.utc)
            except (IndexError, KeyError, ValueError):
                continue
            if filed < since_utc:
                continue
            accession = str(recent["accessionNumber"][index])
            primary_document = str(recent["primaryDocument"][index])
            accession_path = accession.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_path}/{primary_document}"
            )
            title = f"{company.ticker} 提交 SEC {form} 文件"
            descriptions = recent.get("primaryDocDescription") or []
            description = str(
                descriptions[index] if index < len(descriptions) else ""
            )
            results.append(
                ContentItem(
                    id=self._generate_id("sec", form.lower(), accession),
                    source_type=self.SOURCE_TYPE,
                    title=title,
                    url=url,
                    content=f"{payload.get('name', company.ticker)} filed {form}. {description}",
                    author="SEC EDGAR",
                    published_at=filed,
                    profile=self.sec_config.profile,
                    metadata={
                        "source_name": f"SEC EDGAR / {company.ticker}",
                        "source_tier": self.sec_config.tier,
                        "category": self.sec_config.category,
                        "ticker": company.ticker,
                        "form": form,
                        "accession": accession,
                    },
                )
            )
            if len(results) >= self.sec_config.max_per_company:
                break
        return results
