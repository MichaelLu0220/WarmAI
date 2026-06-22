import argparse
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from warmai.evaluation.experiment_log import (
    DEFAULT_LOG_PATH,
    CandidateDecision,
    ExperimentEvent,
    append_event,
    dataset_hash,
    load_events,
    rebuild_state,
)
from warmai.evaluation.suite import DEFAULT_DATASETS, run_suite, write_suite_report

OptimizerMode = Literal["prompt", "rubric"]
DEFAULT_DATASET_PATHS = tuple(dataset.path for dataset in DEFAULT_DATASETS)

DEFAULT_PROMPT_VARIANTS = (
    "Candidate guidance: Prefer suggested_text: null unless a careful human would "
    "fail to understand the original input.",
    "Candidate guidance: Treat short but clear tasks as valid tasks; do not lower "
    "the score only because the wording is brief.",
    "Candidate guidance: Only correct wording when the correction is obvious and "
    "preserves the user's original intent.",
)
DEFAULT_RUBRIC_VARIANTS = (
    "Candidate rubric: When a task implies planning, coordination, or sustained "
    "effort, prefer score 4 over score 3.",
    "Candidate rubric: When a task is a single concrete action that usually takes "
    "under 15 minutes, prefer score 1 or 2.",
    "Candidate rubric: Use score 5 only for large, risky, multi-session, or "
    "high-consequence tasks.",
)


@dataclass(frozen=True)
class OptimizationMetrics:
    overall_passed: bool
    score_within_one_rate: float
    valid_json_rate: float
    language_preservation_rate: float
    http_contract_pass_rate: float
    unnecessary_correction_rate: float
    fallback_rate: float
    p95_latency_ms: int

    def to_event_metrics(self) -> dict[str, float | int | bool | str | None]:
        return {
            "overall_passed": self.overall_passed,
            "score_within_one_rate": self.score_within_one_rate,
            "valid_json_rate": self.valid_json_rate,
            "language_preservation_rate": self.language_preservation_rate,
            "http_contract_pass_rate": self.http_contract_pass_rate,
            "unnecessary_correction_rate": self.unnecessary_correction_rate,
            "fallback_rate": self.fallback_rate,
            "p95_latency_ms": self.p95_latency_ms,
        }

    @classmethod
    def from_event_metrics(
        cls,
        metrics: dict[str, float | int | bool | str | None],
    ) -> "OptimizationMetrics | None":
        required = (
            "overall_passed",
            "score_within_one_rate",
            "valid_json_rate",
            "language_preservation_rate",
            "http_contract_pass_rate",
            "unnecessary_correction_rate",
            "fallback_rate",
            "p95_latency_ms",
        )
        if any(key not in metrics for key in required):
            return None
        return cls(
            overall_passed=bool(metrics["overall_passed"]),
            score_within_one_rate=_metric_float(metrics["score_within_one_rate"]),
            valid_json_rate=_metric_float(metrics["valid_json_rate"]),
            language_preservation_rate=_metric_float(metrics["language_preservation_rate"]),
            http_contract_pass_rate=_metric_float(metrics["http_contract_pass_rate"]),
            unnecessary_correction_rate=_metric_float(metrics["unnecessary_correction_rate"]),
            fallback_rate=_metric_float(metrics["fallback_rate"]),
            p95_latency_ms=_metric_int(metrics["p95_latency_ms"]),
        )


@dataclass(frozen=True)
class DecisionResult:
    decision: CandidateDecision
    reason: str


@dataclass(frozen=True)
class StabilityResult:
    stable: bool
    reason: str


@dataclass(frozen=True)
class CandidateSnapshot:
    model_config_path: Path
    original_model_config: str
    created_prompt_path: Path

    def restore(self) -> None:
        self.model_config_path.write_text(self.original_model_config, encoding="utf-8")
        if self.created_prompt_path.exists():
            self.created_prompt_path.unlink()


@dataclass(frozen=True)
class CandidatePlan:
    baseline_id: str
    candidate_id: str
    changed_factor: str
    prompt_version: str
    prompt_path: Path
    changed_files: list[str]
    snapshot: CandidateSnapshot

    def restore(self) -> None:
        self.snapshot.restore()


@dataclass(frozen=True)
class OptimizerConfig:
    rounds: int
    mode: OptimizerMode
    log_path: Path = DEFAULT_LOG_PATH
    prompt_dir: Path = Path("src") / "warmai" / "inference" / "prompts"
    model_config_path: Path = Path("src") / "warmai" / "config" / "model_config.py"
    dataset_paths: tuple[Path, ...] = DEFAULT_DATASET_PATHS
    accepted_threshold: int = 5
    stability_runs: int = 3
    stability_latency_ratio: float = 1.5
    stability_rate_tolerance: float = 0.05
    stability_critical_tolerance: float = 0.02
    base_url: str = "http://127.0.0.1:8000"
    api_key: str = "dev-secret"
    reload_wait_seconds: float = 0.0
    candidate_prompt_version: str | None = None
    generate_only: bool = False
    allow_manual_candidate: bool = False


class PromptCandidateGenerator:
    def __init__(
        self,
        *,
        prompt_dir: Path,
        model_config_path: Path,
        prompt_variants: Sequence[str] = DEFAULT_PROMPT_VARIANTS,
        rubric_variants: Sequence[str] = DEFAULT_RUBRIC_VARIANTS,
    ) -> None:
        self.prompt_dir = prompt_dir
        self.model_config_path = model_config_path
        self.prompt_variants = tuple(prompt_variants)
        self.rubric_variants = tuple(rubric_variants)

    def create_candidate(
        self,
        *,
        round_index: int,
        mode: OptimizerMode,
        baseline_id: str,
        candidate_prompt_version: str | None = None,
    ) -> CandidatePlan:
        original_config = self.model_config_path.read_text(encoding="utf-8")
        active_prompt_version = _read_prompt_version(original_config)
        active_prompt_path = self.prompt_dir / f"{active_prompt_version}.txt"
        prompt_text = active_prompt_path.read_text(encoding="utf-8")
        prompt_version = candidate_prompt_version or _next_prompt_version(
            active_prompt_version,
            round_index,
        )
        prompt_path = self.prompt_dir / f"{prompt_version}.txt"
        if prompt_path.exists():
            raise FileExistsError(f"Candidate prompt already exists: {prompt_path}")
        variant = self._variant(round_index, mode)
        prompt_path.write_text(_append_variant(prompt_text, variant), encoding="utf-8")
        self.model_config_path.write_text(
            _replace_prompt_version(original_config, prompt_version),
            encoding="utf-8",
        )
        changed_factor = "prompt" if mode == "prompt" else "scoring_rubric"
        return CandidatePlan(
            baseline_id=baseline_id,
            candidate_id=f"{baseline_id}-{mode}-{round_index:04d}",
            changed_factor=changed_factor,
            prompt_version=prompt_version,
            prompt_path=prompt_path,
            changed_files=[
                str(prompt_path),
                str(self.model_config_path),
            ],
            snapshot=CandidateSnapshot(
                model_config_path=self.model_config_path,
                original_model_config=original_config,
                created_prompt_path=prompt_path,
            ),
        )

    def _variant(self, round_index: int, mode: OptimizerMode) -> str:
        variants = self.prompt_variants if mode == "prompt" else self.rubric_variants
        if not variants:
            raise ValueError(f"{mode} variants must not be empty")
        return variants[(round_index - 1) % len(variants)]


class OptimizationRunner:
    def __init__(
        self,
        config: OptimizerConfig,
        *,
        suite_runner: Callable[[], OptimizationMetrics] | None = None,
        generator: PromptCandidateGenerator | None = None,
    ) -> None:
        self.config = config
        self.suite_runner = suite_runner or self._run_live_suite
        self.generator = generator or PromptCandidateGenerator(
            prompt_dir=config.prompt_dir,
            model_config_path=config.model_config_path,
        )
        if not 3 <= config.stability_runs <= 5:
            raise ValueError("stability_runs must be between 3 and 5")

    def run(self) -> None:
        if self.config.generate_only:
            if not self.config.allow_manual_candidate:
                raise RuntimeError(
                    "Manual candidate generation is disabled. Use strict optimize mode, "
                    "or pass --allow-manual-candidate for an explicit step-10-only run."
                )
            self._generate_only()
            return
        for round_index in range(1, self.config.rounds + 1):
            baseline_id, baseline_metrics = self._ensure_flow_baseline()
            events = load_events(self.config.log_path)
            state = rebuild_state(events)
            plan = self.generator.create_candidate(
                round_index=round_index,
                mode=self.config.mode,
                baseline_id=baseline_id,
                candidate_prompt_version=(
                    self.config.candidate_prompt_version if round_index == 1 else None
                ),
            )
            if self.config.reload_wait_seconds > 0:
                time.sleep(self.config.reload_wait_seconds)
            candidate_metrics = self.suite_runner()
            decision = decide_candidate(baseline_metrics, candidate_metrics)
            accepted_since_last_commit = state.accepted_since_last_commit
            if decision.decision == "accepted":
                accepted_since_last_commit += 1
            else:
                plan.restore()
            append_event(
                self.config.log_path,
                ExperimentEvent(
                    event_type="candidate_result",
                    run_id=_run_id(round_index),
                    timestamp=_timestamp(),
                    baseline_id=baseline_id,
                    candidate_id=plan.candidate_id,
                    changed_factor=plan.changed_factor,
                    changed_files=plan.changed_files,
                    dataset_hash=self._current_dataset_hash(),
                    metrics=candidate_metrics.to_event_metrics(),
                    decision=decision.decision,
                    accepted_since_last_commit=accepted_since_last_commit,
                    reason=decision.reason,
                ),
            )
            if decision.decision == "accepted":
                next_baseline_id = _next_baseline_id(baseline_id)
                if accepted_since_last_commit >= self.config.accepted_threshold:
                    append_event(
                        self.config.log_path,
                        ExperimentEvent(
                            event_type="batch_commit_ready",
                            run_id=_run_id(round_index),
                            timestamp=_timestamp(),
                            baseline_id=next_baseline_id,
                            accepted_since_last_commit=accepted_since_last_commit,
                            reason="Accepted candidate threshold reached.",
                        ),
                    )

    def _generate_only(self) -> None:
        state = rebuild_state(load_events(self.config.log_path))
        baseline_id = state.current_baseline_id or "baseline-a"
        plan = self.generator.create_candidate(
            round_index=1,
            mode=self.config.mode,
            baseline_id=baseline_id,
            candidate_prompt_version=self.config.candidate_prompt_version,
        )
        append_event(
            self.config.log_path,
            ExperimentEvent(
                event_type="candidate_started",
                run_id=_run_id(1),
                timestamp=_timestamp(),
                baseline_id=baseline_id,
                candidate_id=plan.candidate_id,
                changed_factor=plan.changed_factor,
                changed_files=plan.changed_files,
                reason="Generated candidate prompt without running evaluation.",
            ),
        )

    def _ensure_flow_baseline(self) -> tuple[str, OptimizationMetrics]:
        events = load_events(self.config.log_path)
        state = rebuild_state(events)
        baseline_id = state.current_baseline_id or "baseline-a"
        current_dataset_hash = self._current_dataset_hash()
        baseline_metrics = _baseline_metrics_for(events, baseline_id)

        if baseline_metrics is None or state.last_dataset_hash != current_dataset_hash:
            baseline_metrics = self.suite_runner()
            append_event(
                self.config.log_path,
                ExperimentEvent(
                    event_type="baseline_created",
                    run_id=_run_id(0),
                    timestamp=_timestamp(),
                    baseline_id=baseline_id,
                    dataset_hash=current_dataset_hash,
                    metrics=baseline_metrics.to_event_metrics(),
                    reason="Flow steps 1-4: fixed current version and created baseline.",
                ),
            )
            events = load_events(self.config.log_path)

        stability_metrics = _stability_metrics_for(events, baseline_id, current_dataset_hash)
        while len(stability_metrics) < self.config.stability_runs:
            run_number = len(stability_metrics) + 1
            metrics = self.suite_runner()
            append_event(
                self.config.log_path,
                ExperimentEvent(
                    event_type="stability_run",
                    run_id=_run_id(run_number),
                    timestamp=_timestamp(),
                    baseline_id=baseline_id,
                    dataset_hash=current_dataset_hash,
                    metrics=metrics.to_event_metrics(),
                    reason=f"Flow steps 5-6: stability run {run_number}.",
                ),
            )
            stability_metrics.append(metrics)

        stability = assess_baseline_stability(
            baseline_metrics,
            stability_metrics[-self.config.stability_runs :],
            latency_ratio=self.config.stability_latency_ratio,
            rate_tolerance=self.config.stability_rate_tolerance,
            critical_tolerance=self.config.stability_critical_tolerance,
        )
        if not stability.stable:
            raise RuntimeError(f"Baseline stability gate failed: {stability.reason}")
        return baseline_id, baseline_metrics

    def _current_dataset_hash(self) -> str:
        return dataset_hash(list(self.config.dataset_paths))

    def _run_live_suite(self) -> OptimizationMetrics:
        results = run_suite(self.config.base_url, self.config.api_key)
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        write_suite_report(Path("reports") / "suite", results, run_id)
        return metrics_from_suite_results(results)


def decide_candidate(
    baseline: OptimizationMetrics,
    candidate: OptimizationMetrics,
) -> DecisionResult:
    if not candidate.overall_passed:
        return DecisionResult("rejected", "Evaluation suite failed.")
    if (
        candidate.valid_json_rate < baseline.valid_json_rate
        or candidate.language_preservation_rate < baseline.language_preservation_rate
        or candidate.http_contract_pass_rate < baseline.http_contract_pass_rate
    ):
        return DecisionResult("rejected", "Critical stability metric regressed.")
    if candidate.score_within_one_rate > baseline.score_within_one_rate:
        return DecisionResult("accepted", "Score accuracy improved.")
    if (
        candidate.score_within_one_rate == baseline.score_within_one_rate
        and candidate.unnecessary_correction_rate < baseline.unnecessary_correction_rate
    ):
        return DecisionResult("accepted", "Unnecessary correction rate improved.")
    if (
        candidate.score_within_one_rate == baseline.score_within_one_rate
        and candidate.unnecessary_correction_rate == baseline.unnecessary_correction_rate
        and candidate.p95_latency_ms < baseline.p95_latency_ms
    ):
        return DecisionResult("accepted", "Latency improved without quality regression.")
    return DecisionResult("rejected", "No accepted metric improved.")


def assess_baseline_stability(
    baseline: OptimizationMetrics,
    stability_runs: Sequence[OptimizationMetrics],
    *,
    latency_ratio: float,
    rate_tolerance: float = 0.05,
    critical_tolerance: float = 0.02,
) -> StabilityResult:
    """Gate the baseline on run-to-run dispersion, not a one-directional compare.

    The flow asks whether each metric "drifts" (飄), which is variance in both
    directions. We pool the baseline run with its stability runs and fail when the
    spread (max - min) of any metric exceeds its tolerance. Critical contract
    metrics (valid JSON, language) get a tight tolerance; fuzzier rates (score,
    HTTP contract that now includes task-intent, unnecessary correction) get a
    wider one. Latency is checked as a relative spread (max <= min * ratio).
    """
    if not baseline.overall_passed:
        return StabilityResult(False, "Baseline evaluation suite failed.")
    if not stability_runs:
        return StabilityResult(False, "No stability runs recorded.")
    runs = [baseline, *stability_runs]
    for metrics in runs:
        if not metrics.overall_passed:
            return StabilityResult(False, "A stability run failed the evaluation suite.")

    def spread(getter: Callable[[OptimizationMetrics], float]) -> float:
        values = [getter(metrics) for metrics in runs]
        return max(values) - min(values)

    checks: tuple[tuple[str, float, float], ...] = (
        ("valid_json_rate", spread(lambda m: m.valid_json_rate), critical_tolerance),
        (
            "language_preservation_rate",
            spread(lambda m: m.language_preservation_rate),
            critical_tolerance,
        ),
        ("http_contract_pass_rate", spread(lambda m: m.http_contract_pass_rate), rate_tolerance),
        ("score_within_one_rate", spread(lambda m: m.score_within_one_rate), rate_tolerance),
        (
            "unnecessary_correction_rate",
            spread(lambda m: m.unnecessary_correction_rate),
            rate_tolerance,
        ),
    )
    for name, observed, tolerance in checks:
        if observed > tolerance:
            return StabilityResult(
                False,
                f"{name} drifted by {observed:.3f} across runs (tolerance {tolerance:.3f}).",
            )

    latencies = [metrics.p95_latency_ms for metrics in runs]
    lowest = min(latencies)
    if lowest > 0 and max(latencies) > int(lowest * latency_ratio):
        return StabilityResult(False, "Latency spread exceeded the stability ratio.")
    return StabilityResult(True, "Baseline stability gate passed.")


def metrics_from_suite_results(results: object) -> OptimizationMetrics:
    summaries = [result.summary for result in results]  # type: ignore[attr-defined]
    passed = all(result.passed for result in results)  # type: ignore[attr-defined]
    return OptimizationMetrics(
        overall_passed=passed,
        score_within_one_rate=min(item.score_within_one_rate for item in summaries),
        valid_json_rate=min(item.valid_json_rate for item in summaries),
        language_preservation_rate=min(item.language_preservation_rate for item in summaries),
        http_contract_pass_rate=min(item.http_contract_pass_rate for item in summaries),
        unnecessary_correction_rate=max(item.unnecessary_correction_rate for item in summaries),
        fallback_rate=max(item.fallback_rate for item in summaries),
        p95_latency_ms=max(item.p95_latency_ms for item in summaries),
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=args.rounds,
            mode=args.mode,
            log_path=args.log_path,
            prompt_dir=args.prompt_dir,
            model_config_path=args.model_config_path,
            accepted_threshold=args.accepted_threshold,
            stability_runs=args.stability_runs,
            stability_latency_ratio=args.stability_latency_ratio,
            stability_rate_tolerance=args.stability_rate_tolerance,
            stability_critical_tolerance=args.stability_critical_tolerance,
            base_url=args.base_url,
            api_key=args.api_key,
            reload_wait_seconds=args.reload_wait_seconds,
            candidate_prompt_version=args.candidate_prompt_version,
            generate_only=args.generate_only,
            allow_manual_candidate=args.allow_manual_candidate,
        )
    )
    runner.run()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--mode", choices=["prompt", "rubric"], default="prompt")
    parser.add_argument("--accepted-threshold", type=int, default=5)
    parser.add_argument("--stability-runs", type=int, default=3)
    parser.add_argument("--stability-latency-ratio", type=float, default=1.5)
    parser.add_argument("--stability-rate-tolerance", type=float, default=0.05)
    parser.add_argument("--stability-critical-tolerance", type=float, default=0.02)
    parser.add_argument("--candidate-prompt-version")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--allow-manual-candidate", action="store_true")
    parser.add_argument("--reload-wait-seconds", type=float, default=0.0)
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=Path("src") / "warmai" / "inference" / "prompts",
    )
    parser.add_argument(
        "--model-config-path",
        type=Path,
        default=Path("src") / "warmai" / "config" / "model_config.py",
    )
    return parser.parse_args(argv)


def _append_variant(prompt_text: str, variant: str) -> str:
    variant_line = "- " + variant
    lines = prompt_text.rstrip("\n").splitlines()
    for index, line in enumerate(lines):
        if line == "{retry_note}" or line.startswith("Task:"):
            return "\n".join([*lines[:index], variant_line, *lines[index:]]) + "\n"
    return "\n".join([*lines, variant_line]) + "\n"


def _next_prompt_version(active_prompt_version: str, round_index: int) -> str:
    match = re.match(r"^(.*?)(\d+)$", active_prompt_version)
    if match is None:
        return f"{active_prompt_version}-candidate-{round_index:04d}"
    prefix, numeric_suffix = match.groups()
    return f"{prefix}{int(numeric_suffix) + 1:0{len(numeric_suffix)}d}"


def _metric_float(value: float | int | bool | str | None) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError("numeric metric must be a number")
    return float(value)


def _metric_int(value: float | int | bool | str | None) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("integer metric must be a number")
    return int(value)


def _read_prompt_version(model_config: str) -> str:
    for line in model_config.splitlines():
        if line.startswith("PROMPT_VERSION = "):
            return line.split("=", maxsplit=1)[1].strip().strip('"')
    raise ValueError("PROMPT_VERSION assignment not found")


def _replace_prompt_version(model_config: str, prompt_version: str) -> str:
    lines = []
    replaced = False
    for line in model_config.splitlines():
        if line.startswith("PROMPT_VERSION = "):
            lines.append(f'PROMPT_VERSION = "{prompt_version}"')
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        raise ValueError("PROMPT_VERSION assignment not found")
    return "\n".join(lines) + "\n"


def _latest_baseline_metrics(events: list[ExperimentEvent]) -> OptimizationMetrics | None:
    for event in reversed(events):
        if event.event_type == "baseline_created" or (
            event.event_type == "candidate_result" and event.decision == "accepted"
        ):
            metrics = OptimizationMetrics.from_event_metrics(event.metrics)
            if metrics is not None:
                return metrics
    return None


def _baseline_metrics_for(
    events: list[ExperimentEvent],
    baseline_id: str,
) -> OptimizationMetrics | None:
    for event in reversed(events):
        if event.event_type == "baseline_created" and event.baseline_id == baseline_id:
            metrics = OptimizationMetrics.from_event_metrics(event.metrics)
            if metrics is not None:
                return metrics
        if (
            event.event_type == "candidate_result"
            and event.decision == "accepted"
            and _next_baseline_id(event.baseline_id) == baseline_id
        ):
            metrics = OptimizationMetrics.from_event_metrics(event.metrics)
            if metrics is not None:
                return metrics
    return None


def _stability_metrics_for(
    events: list[ExperimentEvent],
    baseline_id: str,
    current_dataset_hash: str,
) -> list[OptimizationMetrics]:
    metrics: list[OptimizationMetrics] = []
    for event in events:
        if (
            event.event_type == "stability_run"
            and event.baseline_id == baseline_id
            and event.dataset_hash == current_dataset_hash
        ):
            parsed = OptimizationMetrics.from_event_metrics(event.metrics)
            if parsed is not None:
                metrics.append(parsed)
    return metrics


def _next_baseline_id(baseline_id: str) -> str:
    prefix = "baseline-"
    if not baseline_id.startswith(prefix):
        return f"{baseline_id}-next"
    suffix = baseline_id.removeprefix(prefix)
    if len(suffix) == 1 and "a" <= suffix <= "y":
        return f"{prefix}{chr(ord(suffix) + 1)}"
    return f"{baseline_id}-next"


def _run_id(round_index: int) -> str:
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-r{round_index:04d}"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    main()
