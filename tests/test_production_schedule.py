"""Static checks for the production AI schedule and no-AI briefing reuse."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_full_pipeline_runs_only_at_nine_and_eighteen_eastern() -> None:
    workflow = (ROOT / ".github/workflows/refresh-dashboard.yml").read_text()

    assert 'cron: "0 13,14,22,23 * * *"' in workflow
    assert "TZ=America/New_York" in workflow
    assert '"09"' in workflow
    assert '"18"' in workflow
    assert workflow.count('run: horizon --hours "$WINDOW_HOURS"') == 1


def test_daily_briefing_reuses_snapshot_without_ai_calls() -> None:
    workflow = (ROOT / ".github/workflows/daily-briefing.yml").read_text()

    assert "OPENAI_API_KEY" not in workflow
    assert "run: horizon " not in workflow
    assert "reused existing dashboard snapshot (no AI calls)" in workflow


def test_analysis_cache_is_persisted_on_data_branch() -> None:
    workflow = (ROOT / ".github/workflows/refresh-dashboard.yml").read_text()

    assert workflow.count("data/dashboard/analysis-cache.json") >= 3
    assert workflow.count("data/dashboard/source-state.json") >= 3
