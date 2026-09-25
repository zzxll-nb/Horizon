from src.ai.tokens import get_usage_snapshot, record_usage, reset_usage, usage_phase


def test_usage_is_reported_by_provider_and_pipeline_phase() -> None:
    reset_usage()
    with usage_phase("mini"):
        record_usage("openai", input_tokens=100, output_tokens=20)
    with usage_phase("terra_review"):
        record_usage("openai", input_tokens=50, output_tokens=10)

    usage = get_usage_snapshot()

    assert usage.per_provider["openai"].total == 180
    assert usage.per_phase["mini"].input_tokens == 100
    assert usage.per_phase["terra_review"].output_tokens == 10
    reset_usage()
