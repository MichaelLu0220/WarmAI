from pathlib import Path

import pytest

from warmai.evaluation.experiment_log import load_events, rebuild_state
from warmai.evaluation.optimizer import (
    DecisionResult,
    OptimizationMetrics,
    OptimizationRunner,
    OptimizerConfig,
    PromptCandidateGenerator,
    assess_baseline_stability,
    decide_candidate,
    main,
)


def _write_prompt_workspace(tmp_path: Path) -> tuple[Path, Path]:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "task-analysis-002.txt").write_text(
        "Prompt version: {prompt_version}\n"
        "Analyze one WarmDock task.\n"
        "- Preserve the input language and meaning.\n"
        "{retry_note}\n"
        "Task: {text}\n",
        encoding="utf-8",
    )
    model_config = tmp_path / "model_config.py"
    model_config.write_text(
        'SCHEMA_VERSION = "1.0"\nPROMPT_VERSION = "task-analysis-002"\nMAX_OUTPUT_TOKENS = 256\n',
        encoding="utf-8",
    )
    return prompt_dir, model_config


def _write_dataset_workspace(tmp_path: Path) -> tuple[Path, Path]:
    evaluation_dir = tmp_path / "evaluation"
    evaluation_dir.mkdir()
    core = evaluation_dir / "core.jsonl"
    hard_cases = evaluation_dir / "hard_cases.jsonl"
    core.write_text('{"case_id":"core"}\n', encoding="utf-8")
    hard_cases.write_text('{"case_id":"hard"}\n', encoding="utf-8")
    return core, hard_cases


def _metrics(
    *,
    score: float = 0.8,
    valid_json: float = 1.0,
    language: float = 1.0,
    http: float = 1.0,
    unnecessary: float = 0.2,
    latency: int = 3000,
    passed: bool = True,
) -> OptimizationMetrics:
    return OptimizationMetrics(
        overall_passed=passed,
        score_within_one_rate=score,
        valid_json_rate=valid_json,
        language_preservation_rate=language,
        http_contract_pass_rate=http,
        unnecessary_correction_rate=unnecessary,
        fallback_rate=0.0,
        p95_latency_ms=latency,
    )


def test_prompt_candidate_generator_creates_prompt_and_updates_version(
    tmp_path: Path,
) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    generator = PromptCandidateGenerator(
        prompt_dir=prompt_dir,
        model_config_path=model_config,
        prompt_variants=("Prefer null suggested_text unless the correction is obvious.",),
    )

    plan = generator.create_candidate(
        round_index=1,
        mode="prompt",
        baseline_id="baseline-a",
    )

    assert plan.candidate_id == "baseline-a-prompt-0001"
    assert plan.changed_factor == "prompt"
    assert plan.prompt_version == "task-analysis-003"
    assert plan.prompt_path.exists()
    candidate_prompt = plan.prompt_path.read_text(encoding="utf-8")
    assert "Prefer null suggested_text" in candidate_prompt
    assert candidate_prompt.index("Prefer null suggested_text") < candidate_prompt.index(
        "Task: {text}"
    )
    assert 'PROMPT_VERSION = "task-analysis-003"' in model_config.read_text(encoding="utf-8")


def test_prompt_candidate_generator_can_use_explicit_prompt_version(
    tmp_path: Path,
) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    generator = PromptCandidateGenerator(
        prompt_dir=prompt_dir,
        model_config_path=model_config,
        prompt_variants=("Prefer null suggested_text unless the correction is obvious.",),
    )

    plan = generator.create_candidate(
        round_index=1,
        mode="prompt",
        baseline_id="baseline-a",
        candidate_prompt_version="task-analysis-003",
    )

    assert plan.candidate_id == "baseline-a-prompt-0001"
    assert plan.prompt_version == "task-analysis-003"
    assert plan.prompt_path == prompt_dir / "task-analysis-003.txt"
    assert plan.prompt_path.exists()
    assert 'PROMPT_VERSION = "task-analysis-003"' in model_config.read_text(encoding="utf-8")


def test_candidate_restore_reverts_config_and_deletes_prompt(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    original_config = model_config.read_text(encoding="utf-8")
    generator = PromptCandidateGenerator(
        prompt_dir=prompt_dir,
        model_config_path=model_config,
        prompt_variants=("Prefer null suggested_text unless the correction is obvious.",),
    )
    plan = generator.create_candidate(round_index=1, mode="prompt", baseline_id="baseline-a")

    plan.restore()

    assert model_config.read_text(encoding="utf-8") == original_config
    assert not plan.prompt_path.exists()


def test_prompt_candidate_generator_increments_accepted_numeric_prompt_version(
    tmp_path: Path,
) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    (prompt_dir / "task-analysis-003.txt").write_text(
        "Prompt version: {prompt_version}\n{retry_note}\nTask: {text}\n",
        encoding="utf-8",
    )
    model_config.write_text(
        'SCHEMA_VERSION = "1.0"\nPROMPT_VERSION = "task-analysis-003"\n',
        encoding="utf-8",
    )
    generator = PromptCandidateGenerator(
        prompt_dir=prompt_dir,
        model_config_path=model_config,
        prompt_variants=("Prefer null suggested_text unless the correction is obvious.",),
    )

    plan = generator.create_candidate(
        round_index=1,
        mode="prompt",
        baseline_id="baseline-b",
    )

    assert plan.candidate_id == "baseline-b-prompt-0001"
    assert plan.prompt_version == "task-analysis-004"
    assert plan.prompt_path == prompt_dir / "task-analysis-004.txt"
    assert 'PROMPT_VERSION = "task-analysis-004"' in model_config.read_text(encoding="utf-8")


def test_decision_rejects_critical_regression() -> None:
    decision = decide_candidate(
        baseline=_metrics(score=0.8, valid_json=1.0),
        candidate=_metrics(score=1.0, valid_json=0.9),
    )

    assert decision == DecisionResult(
        decision="rejected",
        reason="Critical stability metric regressed.",
    )


def test_decision_accepts_score_improvement() -> None:
    decision = decide_candidate(
        baseline=_metrics(score=0.8),
        candidate=_metrics(score=1.0),
    )

    assert decision.decision == "accepted"
    assert "Score accuracy improved" in decision.reason


def test_decision_accepts_lower_unnecessary_correction_when_score_is_equal() -> None:
    decision = decide_candidate(
        baseline=_metrics(score=1.0, unnecessary=0.2),
        candidate=_metrics(score=1.0, unnecessary=0.0),
    )

    assert decision.decision == "accepted"
    assert "Unnecessary correction rate improved" in decision.reason


def test_decision_rejects_equal_quality_with_worse_latency() -> None:
    decision = decide_candidate(
        baseline=_metrics(score=1.0, unnecessary=0.0, latency=2000),
        candidate=_metrics(score=1.0, unnecessary=0.0, latency=3000),
    )

    assert decision.decision == "rejected"
    assert "No accepted metric improved" in decision.reason


def test_runner_creates_baseline_then_accepts_candidate(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    dataset_paths = _write_dataset_workspace(tmp_path)
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_calls = [
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=1.0),
    ]

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=1,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            dataset_paths=dataset_paths,
            accepted_threshold=5,
        ),
        suite_runner=lambda: suite_calls.pop(0),
    )

    runner.run()

    events = load_events(log_path)
    state = rebuild_state(events)
    assert [event.event_type for event in events] == [
        "baseline_created",
        "stability_run",
        "stability_run",
        "stability_run",
        "candidate_result",
    ]
    assert events[-1].decision == "accepted"
    assert state.accepted_since_last_commit == 1
    assert (prompt_dir / "task-analysis-003.txt").exists()


def test_runner_rejects_candidate_and_restores_files(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    dataset_paths = _write_dataset_workspace(tmp_path)
    original_config = model_config.read_text(encoding="utf-8")
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_calls = [
        _metrics(score=1.0),
        _metrics(score=1.0),
        _metrics(score=1.0),
        _metrics(score=1.0),
        _metrics(score=1.0, valid_json=0.9),
    ]

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=1,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            dataset_paths=dataset_paths,
            accepted_threshold=5,
        ),
        suite_runner=lambda: suite_calls.pop(0),
    )

    runner.run()

    events = load_events(log_path)
    assert events[-1].decision == "rejected"
    assert model_config.read_text(encoding="utf-8") == original_config
    assert not (prompt_dir / "task-analysis-003.txt").exists()


def test_runner_writes_batch_ready_when_threshold_is_reached(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    dataset_paths = _write_dataset_workspace(tmp_path)
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_calls = [
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=1.0),
    ]

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=1,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            dataset_paths=dataset_paths,
            accepted_threshold=1,
        ),
        suite_runner=lambda: suite_calls.pop(0),
    )

    runner.run()

    events = load_events(log_path)
    assert [event.event_type for event in events] == [
        "baseline_created",
        "stability_run",
        "stability_run",
        "stability_run",
        "candidate_result",
        "batch_commit_ready",
    ]
    assert events[-1].accepted_since_last_commit == 1


def test_stability_gate_passes_when_runs_are_tight() -> None:
    baseline = _metrics(score=0.8)
    runs = [_metrics(score=0.82), _metrics(score=0.78), _metrics(score=0.80)]

    result = assess_baseline_stability(baseline, runs, latency_ratio=1.5)

    assert result.stable is True


def test_stability_gate_catches_upward_drift_old_gate_missed() -> None:
    # Every run is >= baseline, so the old one-directional gate passed. The score
    # still swings 0.20 between runs, which the dispersion gate must reject.
    baseline = _metrics(score=0.80)
    runs = [_metrics(score=1.0), _metrics(score=0.85), _metrics(score=0.90)]

    result = assess_baseline_stability(baseline, runs, latency_ratio=1.5)

    assert result.stable is False
    assert "score_within_one_rate drifted" in result.reason


def test_runner_stops_before_candidate_when_baseline_is_unstable(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    dataset_paths = _write_dataset_workspace(tmp_path)
    original_config = model_config.read_text(encoding="utf-8")
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_calls = [
        _metrics(score=1.0),
        _metrics(score=0.8),
        _metrics(score=1.0),
        _metrics(score=1.0),
    ]

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=1,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            dataset_paths=dataset_paths,
            accepted_threshold=5,
        ),
        suite_runner=lambda: suite_calls.pop(0),
    )

    with pytest.raises(RuntimeError, match="Baseline stability gate failed"):
        runner.run()

    events = load_events(log_path)
    assert [event.event_type for event in events] == [
        "baseline_created",
        "stability_run",
        "stability_run",
        "stability_run",
    ]
    assert model_config.read_text(encoding="utf-8") == original_config
    assert not (prompt_dir / "task-analysis-003.txt").exists()


def test_runner_accepts_003_then_generates_004_after_new_baseline_stability(
    tmp_path: Path,
) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    dataset_paths = _write_dataset_workspace(tmp_path)
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_calls = [
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.8),
        _metrics(score=0.9),
        _metrics(score=0.9),
        _metrics(score=0.9),
        _metrics(score=0.9),
        _metrics(score=1.0),
    ]

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=2,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            dataset_paths=dataset_paths,
            accepted_threshold=5,
            candidate_prompt_version="task-analysis-003",
        ),
        suite_runner=lambda: suite_calls.pop(0),
    )

    runner.run()

    events = load_events(log_path)
    candidate_events = [event for event in events if event.event_type == "candidate_result"]
    stability_events = [event for event in events if event.event_type == "stability_run"]
    assert [event.candidate_id for event in candidate_events] == [
        "baseline-a-prompt-0001",
        "baseline-b-prompt-0002",
    ]
    assert candidate_events[0].decision == "accepted"
    assert candidate_events[1].decision == "accepted"
    assert len(stability_events) == 6
    assert (prompt_dir / "task-analysis-003.txt").exists()
    assert (prompt_dir / "task-analysis-004.txt").exists()
    assert 'PROMPT_VERSION = "task-analysis-004"' in model_config.read_text(encoding="utf-8")


def test_runner_generate_only_creates_candidate_without_suite_decision(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    log_path = tmp_path / "warmai-experiments.jsonl"
    suite_calls = 0

    def suite_runner() -> OptimizationMetrics:
        nonlocal suite_calls
        suite_calls += 1
        return _metrics(score=1.0)

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=1,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            accepted_threshold=5,
            candidate_prompt_version="task-analysis-003",
            generate_only=True,
            allow_manual_candidate=True,
        ),
        suite_runner=suite_runner,
    )

    runner.run()

    events = load_events(log_path)
    assert suite_calls == 0
    assert [event.event_type for event in events] == ["candidate_started"]
    assert events[0].candidate_id == "baseline-a-prompt-0001"
    assert (prompt_dir / "task-analysis-003.txt").exists()
    assert 'PROMPT_VERSION = "task-analysis-003"' in model_config.read_text(encoding="utf-8")


def test_runner_generate_only_requires_explicit_manual_override(tmp_path: Path) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    log_path = tmp_path / "warmai-experiments.jsonl"

    runner = OptimizationRunner(
        OptimizerConfig(
            rounds=1,
            mode="prompt",
            log_path=log_path,
            prompt_dir=prompt_dir,
            model_config_path=model_config,
            candidate_prompt_version="task-analysis-003",
            generate_only=True,
        ),
        suite_runner=lambda: _metrics(score=1.0),
    )

    with pytest.raises(RuntimeError, match="Manual candidate generation is disabled"):
        runner.run()

    assert not log_path.exists()
    assert not (prompt_dir / "task-analysis-003.txt").exists()


def test_main_parses_cli_and_runs_optimizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_dir, model_config = _write_prompt_workspace(tmp_path)
    calls: list[OptimizerConfig] = []

    def run(self: OptimizationRunner) -> None:
        calls.append(self.config)

    monkeypatch.setattr("warmai.evaluation.optimizer.OptimizationRunner.run", run)

    main(
        [
            "--rounds",
            "3",
            "--base-url",
            "http://api",
            "--api-key",
            "secret",
            "--mode",
            "prompt",
            "--accepted-threshold",
            "10",
            "--candidate-prompt-version",
            "task-analysis-003",
            "--generate-only",
            "--allow-manual-candidate",
            "--stability-runs",
            "4",
            "--prompt-dir",
            str(prompt_dir),
            "--model-config-path",
            str(model_config),
            "--log-path",
            str(tmp_path / "experiments.jsonl"),
        ]
    )

    assert len(calls) == 1
    assert calls[0].rounds == 3
    assert calls[0].base_url == "http://api"
    assert calls[0].api_key == "secret"
    assert calls[0].mode == "prompt"
    assert calls[0].accepted_threshold == 10
    assert calls[0].candidate_prompt_version == "task-analysis-003"
    assert calls[0].generate_only is True
    assert calls[0].allow_manual_candidate is True
    assert calls[0].stability_runs == 4
