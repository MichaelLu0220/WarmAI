import json
from pathlib import Path

from warmai.evaluation.experiment_log import main


def test_record_candidate_result_cli_appends_event_with_suite_metrics(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_report = tmp_path / "suite.json"
    suite_report.write_text(
        json.dumps(
            {
                "overall_passed": True,
                "datasets": [
                    {
                        "name": "core",
                        "passed": True,
                        "summary": {
                            "score_within_one_rate": 1.0,
                            "valid_json_rate": 1.0,
                            "language_preservation_rate": 1.0,
                            "http_contract_pass_rate": 1.0,
                            "unnecessary_correction_rate": 0.0,
                            "fallback_rate": 0.0,
                            "p95_latency_ms": 120,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    main(
        [
            "--log-path",
            str(log_path),
            "record-candidate-result",
            "--run-id",
            "run-001",
            "--timestamp",
            "2026-06-22T10:20:00+08:00",
            "--baseline-id",
            "baseline-a",
            "--candidate-id",
            "candidate-a1",
            "--changed-factor",
            "prompt",
            "--changed-file",
            "src/warmai/inference/prompts/task-analysis-003.txt",
            "--suite-report",
            str(suite_report),
            "--decision",
            "accepted",
            "--reason",
            "Score improved.",
        ]
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["event_type"] == "candidate_result"
    assert payload["decision"] == "accepted"
    assert payload["accepted_since_last_commit"] == 1
    assert payload["metrics"]["overall_passed"] is True
    assert payload["metrics"]["core.score_within_one_rate"] == 1.0
    assert payload["changed_files"] == ["src/warmai/inference/prompts/task-analysis-003.txt"]


def test_show_state_cli_prints_rebuilt_state(tmp_path: Path, capsys: object) -> None:
    log_path = tmp_path / "warmai-experiments.jsonl"
    main(
        [
            "--log-path",
            str(log_path),
            "record-candidate-result",
            "--run-id",
            "run-001",
            "--timestamp",
            "2026-06-22T10:20:00+08:00",
            "--baseline-id",
            "baseline-a",
            "--candidate-id",
            "candidate-a1",
            "--changed-factor",
            "prompt",
            "--decision",
            "accepted",
            "--reason",
            "Score improved.",
        ]
    )

    main(["--log-path", str(log_path), "show-state"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["current_baseline_id"] == "baseline-b"
    assert payload["latest_candidate_id"] == "candidate-a1"
    assert payload["accepted_since_last_commit"] == 1


def test_mark_batch_commit_done_cli_resets_counter(tmp_path: Path, capsys: object) -> None:
    log_path = tmp_path / "warmai-experiments.jsonl"
    main(
        [
            "--log-path",
            str(log_path),
            "record-candidate-result",
            "--run-id",
            "run-001",
            "--timestamp",
            "2026-06-22T10:20:00+08:00",
            "--baseline-id",
            "baseline-a",
            "--candidate-id",
            "candidate-a1",
            "--changed-factor",
            "prompt",
            "--decision",
            "accepted",
            "--reason",
            "Score improved.",
        ]
    )
    main(
        [
            "--log-path",
            str(log_path),
            "mark-batch-commit-done",
            "--run-id",
            "run-002",
            "--timestamp",
            "2026-06-22T10:30:00+08:00",
            "--baseline-id",
            "baseline-b",
            "--reason",
            "Committed one accepted candidate.",
        ]
    )

    main(["--log-path", str(log_path), "show-state"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["current_baseline_id"] == "baseline-b"
    assert payload["accepted_since_last_commit"] == 0


def test_rejected_candidate_does_not_increment_batch_counter(tmp_path: Path) -> None:
    log_path = tmp_path / "warmai-experiments.jsonl"

    main(
        [
            "--log-path",
            str(log_path),
            "record-candidate-result",
            "--run-id",
            "run-001",
            "--timestamp",
            "2026-06-22T10:20:00+08:00",
            "--baseline-id",
            "baseline-a",
            "--candidate-id",
            "candidate-a1",
            "--changed-factor",
            "temperature",
            "--decision",
            "rejected",
            "--reason",
            "Latency regressed.",
        ]
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["decision"] == "rejected"
    assert payload["accepted_since_last_commit"] == 0
