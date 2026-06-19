import json
from pathlib import Path

from warmai.evaluation.metrics import EvaluationSummary
from warmai.evaluation.reporting import write_report


def test_report_writes_fixed_locations(tmp_path: Path) -> None:
    summary = EvaluationSummary(
        total=1,
        score_within_one_rate=1.0,
        valid_json_rate=1.0,
        language_preservation_rate=1.0,
        fallback_rate=0.0,
        unnecessary_correction_rate=0.0,
        p95_latency_ms=100,
    )

    write_report(tmp_path, summary, run_id="run-001")

    latest = tmp_path / "latest.json"
    history = tmp_path / "history" / "run-001.json"
    markdown = tmp_path / "summary.md"
    assert latest.exists()
    assert history.exists()
    assert markdown.exists()
    assert json.loads(latest.read_text(encoding="utf-8")) == {
        "fallback_rate": 0.0,
        "language_preservation_rate": 1.0,
        "p95_latency_ms": 100,
        "score_within_one_rate": 1.0,
        "total": 1,
        "unnecessary_correction_rate": 0.0,
        "valid_json_rate": 1.0,
    }
    assert history.read_text(encoding="utf-8") == latest.read_text(encoding="utf-8")
    assert "Score within 1: 100.0%" in markdown.read_text(encoding="utf-8")
