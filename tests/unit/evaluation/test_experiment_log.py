import json
from pathlib import Path

from warmai.evaluation.experiment_log import (
    ExperimentEvent,
    append_event,
    dataset_hash,
    load_events,
    rebuild_state,
)


def test_append_event_writes_one_json_object_per_line(tmp_path: Path) -> None:
    log_path = tmp_path / "reports" / "experiments" / "warmai-experiments.jsonl"
    event = ExperimentEvent(
        event_type="candidate_result",
        run_id="run-001",
        timestamp="2026-06-22T10:20:00+08:00",
        baseline_id="baseline-a",
        candidate_id="candidate-a1",
        changed_factor="prompt",
        decision="accepted",
        reason="Score improved with no stability regression.",
    )

    append_event(log_path, event)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event_type"] == "candidate_result"
    assert payload["candidate_id"] == "candidate-a1"
    assert payload["decision"] == "accepted"


def test_rebuild_state_counts_only_accepted_candidates_since_last_commit(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "warmai-experiments.jsonl"
    events = [
        ExperimentEvent(
            event_type="baseline_created",
            run_id="run-001",
            timestamp="2026-06-22T10:00:00+08:00",
            baseline_id="baseline-a",
        ),
        ExperimentEvent(
            event_type="candidate_result",
            run_id="run-002",
            timestamp="2026-06-22T10:10:00+08:00",
            baseline_id="baseline-a",
            candidate_id="candidate-a1",
            changed_factor="prompt",
            decision="accepted",
        ),
        ExperimentEvent(
            event_type="candidate_result",
            run_id="run-003",
            timestamp="2026-06-22T10:20:00+08:00",
            baseline_id="baseline-b",
            candidate_id="candidate-b1",
            changed_factor="top_p",
            decision="rejected",
        ),
        ExperimentEvent(
            event_type="standard_changed",
            run_id="run-004",
            timestamp="2026-06-22T10:30:00+08:00",
            baseline_id="baseline-b",
            reason="Dataset expanded.",
        ),
        ExperimentEvent(
            event_type="candidate_result",
            run_id="run-005",
            timestamp="2026-06-22T10:40:00+08:00",
            baseline_id="baseline-b",
            candidate_id="candidate-b2",
            changed_factor="MAX_OUTPUT_TOKENS",
            decision="accepted",
        ),
    ]
    for event in events:
        append_event(log_path, event)

    state = rebuild_state(load_events(log_path))

    assert state.current_baseline_id == "baseline-c"
    assert state.latest_candidate_id == "candidate-b2"
    assert state.accepted_since_last_commit == 2
    assert state.accepted_candidates == ["candidate-a1", "candidate-b2"]
    assert state.rejected_candidates == ["candidate-b1"]


def test_batch_commit_done_resets_accepted_counter(tmp_path: Path) -> None:
    log_path = tmp_path / "warmai-experiments.jsonl"
    for event in [
        ExperimentEvent(
            event_type="candidate_result",
            run_id="run-001",
            timestamp="2026-06-22T10:00:00+08:00",
            baseline_id="baseline-a",
            candidate_id="candidate-a1",
            changed_factor="prompt",
            decision="accepted",
        ),
        ExperimentEvent(
            event_type="batch_commit_done",
            run_id="run-002",
            timestamp="2026-06-22T10:10:00+08:00",
            baseline_id="baseline-b",
            reason="Committed accepted candidates a1.",
        ),
    ]:
        append_event(log_path, event)

    state = rebuild_state(load_events(log_path))

    assert state.current_baseline_id == "baseline-b"
    assert state.accepted_since_last_commit == 0


def test_dataset_hash_is_stable_for_ordered_paths(tmp_path: Path) -> None:
    first = tmp_path / "core.jsonl"
    second = tmp_path / "hard_cases.jsonl"
    first.write_text('{"case_id":"core"}\n', encoding="utf-8")
    second.write_text('{"case_id":"hard"}\n', encoding="utf-8")

    digest = dataset_hash([first, second])

    assert digest.startswith("sha256:")
    assert digest == dataset_hash([first, second])
    assert digest != dataset_hash([second, first])
