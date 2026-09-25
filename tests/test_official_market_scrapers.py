from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import asyncio

from src.models import BLSConfig, BLSSeriesConfig, SECCompanyConfig, SECFilingsConfig
from src.scrapers.official_markets import BLSDataScraper, SECFilingsScraper


NOW = datetime.now(timezone.utc)


def response(payload: dict) -> MagicMock:
    value = MagicMock()
    value.status_code = 200
    value.raise_for_status.return_value = None
    value.json.return_value = payload
    return value


def test_bls_baselines_then_emits_changed_official_series() -> None:
    client = AsyncMock()
    client.post.return_value = response(
        {
            "status": "REQUEST_SUCCEEDED",
            "Results": {
                "series": [
                    {
                        "seriesID": "CUUR0000SA0",
                        "data": [
                            {"year": "2026", "period": "M08", "periodName": "August", "value": "321.0", "latest": "true"},
                            {"value": "320.0"},
                        ],
                    }
                ]
            },
        }
    )
    config = BLSConfig(
        enabled=True,
        series=[BLSSeriesConfig(id="CUUR0000SA0", name="CPI", unit="index")],
    )

    first = BLSDataScraper(config, client)
    assert asyncio.run(first.fetch(NOW - timedelta(hours=15))) == []
    second = BLSDataScraper(
        config, client, previous_state={"CUUR0000SA0": "2026:M07:320.0"}
    )
    items = asyncio.run(second.fetch(NOW - timedelta(hours=15)))

    assert len(items) == 1
    assert items[0].metadata["source_tier"] == 1


def test_sec_filters_forms_and_limits_company_results() -> None:
    accepted = NOW.isoformat().replace("+00:00", "Z")
    client = AsyncMock()
    client.get.return_value = response(
        {
            "name": "NVIDIA CORP",
            "filings": {
                "recent": {
                    "form": ["8-K", "4"],
                    "filingDate": [NOW.date().isoformat(), NOW.date().isoformat()],
                    "acceptanceDateTime": [accepted, accepted],
                    "accessionNumber": ["0001-26-000001", "0001-26-000002"],
                    "primaryDocument": ["report.htm", "ownership.xml"],
                    "primaryDocDescription": ["Current report", "Insider form"],
                }
            },
        }
    )
    config = SECFilingsConfig(
        enabled=True,
        companies=[SECCompanyConfig(ticker="NVDA", cik="1045810")],
        forms=["8-K"],
        max_per_company=1,
    )

    items = asyncio.run(SECFilingsScraper(config, client).fetch(NOW - timedelta(hours=1)))

    assert len(items) == 1
    assert items[0].metadata["form"] == "8-K"
    assert items[0].metadata["source_tier"] == 1
