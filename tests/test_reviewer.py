import asyncio
import json
from datetime import datetime, timezone

from src.ai.reviewer import ContentReviewer
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    SourceType,
)


def _item(item_id: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"Title {item_id}",
        url=f"https://example.com/{item_id}",
        published_at=datetime.now(timezone.utc),
        processing=ProcessingResult(
            classification=ClassificationResult(
                profile="finance-news",
                method="source_override",
            ),
            analysis=ContentAnalysis(
                score=7.5,
                reason="initial",
                summary="initial",
            ),
        ),
    )


def _review(item_id: str) -> dict[str, object]:
    return {
        "id": item_id,
        "score": 8.0,
        "decision": "select",
        "reason": "material",
        "hidden_importance": False,
        "second_order_impact": True,
        "cross_asset_impact": False,
        "systemic_risk": False,
        "critical_event": False,
        "complexity": "medium",
    }


def _response(*item_ids: str) -> str:
    return json.dumps({"reviews": [_review(item_id) for item_id in item_ids]})


class ResponseClient:
    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = 0

    async def complete(self, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls += 1
        return next(self.responses)


def test_normal_batch_succeeds_without_fallback() -> None:
    items = [_item("a"), _item("b")]
    client = ResponseClient([_response("a", "b")])

    result = asyncio.run(ContentReviewer(client).review_batch(items))

    assert result.reviewed_ids == ["a", "b"]
    assert result.batch_fallback_count == 0
    assert result.single_item_fallback_count == 0
    assert result.final_review_failure_count == 0


def test_duplicate_id_is_reported_precisely() -> None:
    items = [_item("a"), _item("b")]
    response = json.dumps({"reviews": [_review("a"), _review("a")]})

    reviews, failure = ContentReviewer._parse_reviews(response, items)

    assert reviews is None
    assert failure == "duplicate id 'a'"


def test_missing_id_is_reported_precisely() -> None:
    items = [_item("a"), _item("b")]

    reviews, failure = ContentReviewer._parse_reviews(_response("a"), items)

    assert reviews is None
    assert failure == "missing ids ['b']"


def test_unexpected_id_is_reported_precisely() -> None:
    items = [_item("a")]

    reviews, failure = ContentReviewer._parse_reviews(_response("other"), items)

    assert reviews is None
    assert failure == "unexpected id 'other'"


def test_repair_success_avoids_batch_fallback() -> None:
    items = [_item("a"), _item("b")]
    duplicate = json.dumps({"reviews": [_review("a"), _review("a")]})
    client = ResponseClient([duplicate, _response("a", "b")])

    result = asyncio.run(ContentReviewer(client).review_batch(items))

    assert result.reviewed_ids == ["a", "b"]
    assert client.calls == 2
    assert result.batch_fallback_count == 0


def test_failed_repair_splits_eight_item_batch_into_four_plus_four() -> None:
    items = [_item(str(index)) for index in range(8)]
    invalid = _response("unexpected")
    client = ResponseClient(
        [
            invalid,
            invalid,
            _response("0", "1", "2", "3"),
            _response("4", "5", "6", "7"),
        ]
    )

    result = asyncio.run(ContentReviewer(client).review_batch(items))

    assert result.reviewed_ids == [str(index) for index in range(8)]
    assert result.batch_fallback_count == 1
    assert result.single_item_fallback_count == 0
    assert result.final_review_failure_count == 0


def test_single_item_final_failure_does_not_affect_sibling() -> None:
    items = [_item("good"), _item("bad")]
    invalid_batch = _response("unexpected")
    invalid_single = _response("wrong")
    client = ResponseClient(
        [
            invalid_batch,
            invalid_batch,
            _response("good"),
            invalid_single,
            invalid_single,
        ]
    )

    result = asyncio.run(ContentReviewer(client).review_batch(items))

    assert result.reviewed_ids == ["good"]
    assert set(result.failures) == {"bad"}
    assert "unexpected id" in result.failures["bad"]
    assert result.batch_fallback_count == 1
    assert result.single_item_fallback_count == 2
    assert result.final_review_failure_count == 1
