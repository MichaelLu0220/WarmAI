import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

ExperimentEventType = Literal[
    "baseline_created",
    "stability_run",
    "candidate_started",
    "candidate_result",
    "candidate_accepted",
    "candidate_rejected",
    "standard_changed",
    "batch_commit_ready",
    "batch_commit_done",
]
CandidateDecision = Literal["accepted", "rejected"]
MetricValue = float | int | bool | str | None
DEFAULT_LOG_PATH = Path("reports") / "experiments" / "warmai-experiments.jsonl"


@dataclass(frozen=True)
class ExperimentEvent:
    event_type: ExperimentEventType
    run_id: str
    timestamp: str
    baseline_id: str
    candidate_id: str | None = None
    changed_factor: str | None = None
    changed_files: list[str] = field(default_factory=list)
    dataset_hash: str | None = None
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    decision: CandidateDecision | None = None
    accepted_since_last_commit: int | None = None
    reason: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None and value != [] and value != {}
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ExperimentEvent":
        changed_files = payload.get("changed_files", [])
        metrics = payload.get("metrics", {})
        if not isinstance(changed_files, list):
            raise ValueError("changed_files must be a list")
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be an object")
        return cls(
            event_type=cast(ExperimentEventType, payload["event_type"]),
            run_id=str(payload["run_id"]),
            timestamp=str(payload["timestamp"]),
            baseline_id=str(payload["baseline_id"]),
            candidate_id=payload.get("candidate_id"),
            changed_factor=payload.get("changed_factor"),
            changed_files=[str(item) for item in changed_files],
            dataset_hash=payload.get("dataset_hash"),
            metrics=_coerce_metrics(metrics),
            decision=cast(CandidateDecision | None, payload.get("decision")),
            accepted_since_last_commit=payload.get("accepted_since_last_commit"),
            reason=payload.get("reason"),
        )


@dataclass(frozen=True)
class ExperimentState:
    current_baseline_id: str | None = None
    latest_candidate_id: str | None = None
    accepted_since_last_commit: int = 0
    accepted_candidates: list[str] = field(default_factory=list)
    rejected_candidates: list[str] = field(default_factory=list)
    last_dataset_hash: str | None = None


def append_event(path: Path, event: ExperimentEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event.to_payload(), ensure_ascii=False, sort_keys=True))
        file.write("\n")


def load_events(path: Path) -> list[ExperimentEvent]:
    if not path.exists():
        return []
    events: list[ExperimentEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("experiment log lines must be JSON objects")
            events.append(ExperimentEvent.from_payload(payload))
    return events


def rebuild_state(events: list[ExperimentEvent]) -> ExperimentState:
    current_baseline_id: str | None = None
    latest_candidate_id: str | None = None
    accepted_since_last_commit = 0
    accepted_candidates: list[str] = []
    rejected_candidates: list[str] = []
    last_dataset_hash: str | None = None

    for event in events:
        if event.dataset_hash is not None:
            last_dataset_hash = event.dataset_hash

        if event.event_type == "baseline_created":
            current_baseline_id = event.baseline_id
            continue

        if event.candidate_id is not None:
            latest_candidate_id = event.candidate_id

        if event.event_type == "candidate_result" and event.decision == "accepted":
            if event.candidate_id is not None:
                accepted_candidates.append(event.candidate_id)
            accepted_since_last_commit += 1
            current_baseline_id = _next_baseline_id(event.baseline_id)
            continue

        if event.event_type == "candidate_result" and event.decision == "rejected":
            if event.candidate_id is not None:
                rejected_candidates.append(event.candidate_id)
            current_baseline_id = event.baseline_id
            continue

        if event.event_type == "standard_changed":
            current_baseline_id = event.baseline_id
            continue

        if event.event_type == "batch_commit_done":
            current_baseline_id = event.baseline_id
            accepted_since_last_commit = 0

    return ExperimentState(
        current_baseline_id=current_baseline_id,
        latest_candidate_id=latest_candidate_id,
        accepted_since_last_commit=accepted_since_last_commit,
        accepted_candidates=accepted_candidates,
        rejected_candidates=rejected_candidates,
        last_dataset_hash=last_dataset_hash,
    )


def dataset_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _next_baseline_id(baseline_id: str) -> str:
    prefix = "baseline-"
    if not baseline_id.startswith(prefix):
        return f"{baseline_id}-next"
    suffix = baseline_id.removeprefix(prefix)
    if len(suffix) == 1 and "a" <= suffix <= "y":
        return f"{prefix}{chr(ord(suffix) + 1)}"
    return f"{baseline_id}-next"


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.command == "show-state":
        state = rebuild_state(load_events(args.log_path))
        print(json.dumps(asdict(state), ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "record-candidate-result":
        state = rebuild_state(load_events(args.log_path))
        accepted_since_last_commit = state.accepted_since_last_commit
        if args.decision == "accepted":
            accepted_since_last_commit += 1
        event = ExperimentEvent(
            event_type="candidate_result",
            run_id=args.run_id or _default_run_id(),
            timestamp=args.timestamp or _default_timestamp(),
            baseline_id=args.baseline_id,
            candidate_id=args.candidate_id,
            changed_factor=args.changed_factor,
            changed_files=args.changed_file,
            dataset_hash=args.dataset_hash,
            metrics=_suite_metrics(args.suite_report),
            decision=args.decision,
            accepted_since_last_commit=accepted_since_last_commit,
            reason=args.reason,
        )
        append_event(args.log_path, event)
        return

    if args.command == "mark-batch-commit-done":
        event = ExperimentEvent(
            event_type="batch_commit_done",
            run_id=args.run_id or _default_run_id(),
            timestamp=args.timestamp or _default_timestamp(),
            baseline_id=args.baseline_id,
            reason=args.reason,
        )
        append_event(args.log_path, event)
        return

    raise ValueError(f"Unknown command: {args.command}")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("show-state")

    record = subcommands.add_parser("record-candidate-result")
    record.add_argument("--run-id")
    record.add_argument("--timestamp")
    record.add_argument("--baseline-id", required=True)
    record.add_argument("--candidate-id", required=True)
    record.add_argument("--changed-factor", required=True)
    record.add_argument("--changed-file", action="append", default=[])
    record.add_argument("--dataset-hash")
    record.add_argument("--suite-report", type=Path)
    record.add_argument("--decision", choices=["accepted", "rejected"], required=True)
    record.add_argument("--reason", required=True)

    mark = subcommands.add_parser("mark-batch-commit-done")
    mark.add_argument("--run-id")
    mark.add_argument("--timestamp")
    mark.add_argument("--baseline-id", required=True)
    mark.add_argument("--reason", required=True)

    return parser.parse_args(argv)


def _suite_metrics(path: Path | None) -> dict[str, MetricValue]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("suite report must be a JSON object")

    metrics: dict[str, MetricValue] = {}
    overall_passed = payload.get("overall_passed")
    if isinstance(overall_passed, bool):
        metrics["overall_passed"] = overall_passed

    datasets = payload.get("datasets", [])
    if not isinstance(datasets, list):
        raise ValueError("suite report datasets must be a list")
    for item in datasets:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        passed = item.get("passed")
        if isinstance(passed, bool):
            metrics[f"{name}.passed"] = passed
        summary = item.get("summary", {})
        if not isinstance(summary, dict):
            continue
        for key, value in summary.items():
            if isinstance(key, str) and _is_metric_value(value):
                metrics[f"{name}.{key}"] = value
    return metrics


def _coerce_metrics(metrics: dict[str, Any]) -> dict[str, MetricValue]:
    return {str(key): value for key, value in metrics.items() if _is_metric_value(value)}


def _is_metric_value(value: object) -> bool:
    return isinstance(value, bool | int | float | str) or value is None


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _default_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    main()
