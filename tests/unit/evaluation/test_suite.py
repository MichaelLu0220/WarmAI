import json
from pathlib import Path

import pytest

from warmai.evaluation.metrics import EvaluationSample, EvaluationSummary
from warmai.evaluation.suite import (
    EvaluationDataset,
    SuiteDatasetResult,
    main,
    run_suite,
    write_suite_report,
)


def _summary(score: float = 1.0, http: float = 1.0) -> EvaluationSummary:
    return EvaluationSummary(
        total=1,
        score_within_one_rate=score,
        valid_json_rate=1.0,
        language_preservation_rate=1.0,
        fallback_rate=0.0,
        unnecessary_correction_rate=0.0,
        http_contract_pass_rate=http,
        p95_latency_ms=100,
    )


def _sample(case_id: str = "case-1") -> EvaluationSample:
    return EvaluationSample(
        case_id=case_id,
        text="Clean the desk",
        expected_score=2,
        actual_score=2,
        valid_json=True,
        latency_ms=100,
        expected_language="en",
        actual_language="en",
        status_code=200,
        response_status="ok",
    )


def test_run_suite_evaluates_datasets_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    datasets = [
        EvaluationDataset("core", Path("evaluation/core.jsonl")),
        EvaluationDataset("hard_cases", Path("evaluation/hard_cases.jsonl")),
    ]
    calls: list[Path] = []

    def load_cases(path: Path) -> list[object]:
        calls.append(path)
        return [object()]

    monkeypatch.setattr("warmai.evaluation.suite.load_cases", load_cases)
    monkeypatch.setattr(
        "warmai.evaluation.suite.run_cases",
        lambda cases, base_url, api_key: [_sample()],
    )
    monkeypatch.setattr("warmai.evaluation.suite.summarize", lambda samples: _summary())
    monkeypatch.setattr("warmai.evaluation.suite.passes_mvp_gates", lambda summary: True)

    results = run_suite("http://api", "secret", datasets=datasets)

    assert calls == [Path("evaluation/core.jsonl"), Path("evaluation/hard_cases.jsonl")]
    assert [result.name for result in results] == ["core", "hard_cases"]
    assert all(result.passed for result in results)


def test_write_suite_report_writes_combined_outputs(tmp_path: Path) -> None:
    results = [
        SuiteDatasetResult(
            name="core",
            dataset=Path("evaluation/core.jsonl"),
            summary=_summary(),
            passed=True,
            samples=[_sample("core-1")],
        ),
        SuiteDatasetResult(
            name="hard_cases",
            dataset=Path("evaluation/hard_cases.jsonl"),
            summary=_summary(),
            passed=True,
            samples=[_sample("hard-1")],
        ),
    ]

    write_suite_report(tmp_path, results, run_id="run-001")

    latest = tmp_path / "latest.json"
    history = tmp_path / "history" / "run-001.json"
    summary = tmp_path / "summary.md"
    failures = tmp_path / "failures.md"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["overall_passed"] is True
    assert [item["name"] for item in payload["datasets"]] == ["core", "hard_cases"]
    assert history.read_text(encoding="utf-8") == latest.read_text(encoding="utf-8")
    assert "| core | PASS |" in summary.read_text(encoding="utf-8")
    assert "No failing cases." in failures.read_text(encoding="utf-8")


def test_write_suite_report_lists_failures(tmp_path: Path) -> None:
    failing_sample = EvaluationSample(
        case_id="score-miss",
        text="Clean the desk",
        expected_score=2,
        actual_score=5,
        valid_json=True,
        latency_ms=100,
        expected_language="en",
        actual_language="en",
        status_code=200,
        response_status="ok",
    )
    results = [
        SuiteDatasetResult(
            name="core",
            dataset=Path("evaluation/core.jsonl"),
            summary=_summary(score=0.0),
            passed=False,
            samples=[failing_sample],
        )
    ]

    write_suite_report(tmp_path, results, run_id="run-001")

    failures = (tmp_path / "failures.md").read_text(encoding="utf-8")
    assert "score-miss" in failures
    assert "score_delta_outside_one" in failures


def test_main_exits_zero_when_suite_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = SuiteDatasetResult(
        name="core",
        dataset=Path("evaluation/core.jsonl"),
        summary=_summary(),
        passed=True,
        samples=[_sample()],
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["warmai-evaluate-suite", "--base-url", "http://api", "--api-key", "secret"],
    )
    monkeypatch.setattr("warmai.evaluation.suite.run_suite", lambda base_url, api_key: [result])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 0
    assert (tmp_path / "reports" / "suite" / "latest.json").exists()
