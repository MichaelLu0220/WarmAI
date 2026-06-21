# WarmAI Evaluation Baseline and Failure Report Completion Report

## Scope

- Ran a real llama.cpp-backed baseline evaluation against `evaluation/core.jsonl`.
- Extended `EvaluationSample` with per-case metadata needed for diagnostics.
- Added failure-only report output:
  - `reports/latest_failures.jsonl`
  - `reports/history/<run_id>-failures.jsonl`
  - `reports/failures.md`
- Wired `warmai-evaluate` to pass per-case samples into reporting.
- Ignored generated failure report artifacts in Git.

## Baseline Evidence

Initial baseline before the report change:

```text
total: 5
score_within_one_rate: 0.6
valid_json_rate: 1.0
language_preservation_rate: 1.0
fallback_rate: 0.0
unnecessary_correction_rate: 0.8
p95_latency_ms: 2828
exit code: 1
```

Post-change evaluation produced the same gate result shape and wrote per-case failures:

```text
total: 5
score_within_one_rate: 0.6
valid_json_rate: 1.0
language_preservation_rate: 1.0
fallback_rate: 0.0
unnecessary_correction_rate: 0.8
p95_latency_ms: 2562
exit code: 1
```

The failing score-gate cases were `zh-001` and `ambiguous-001`.

## TDD Evidence

RED:

```text
tests/integration/evaluation/test_reporting.py::test_report_writes_per_case_failures FAILED
TypeError: EvaluationSample.__init__() got an unexpected keyword argument 'case_id'

tests/unit/evaluation/test_runner.py::test_run_cases_collects_http_metrics FAILED
AttributeError: 'EvaluationSample' object has no attribute 'case_id'
```

GREEN:

```text
tests/integration/evaluation/test_reporting.py tests/unit/evaluation/test_runner.py
5 passed in 0.67s
```

## Verification Results

| Check | Result |
| --- | --- |
| Ruff format | 58 files left unchanged |
| Ruff lint | Passed |
| Mypy | No issues in 36 source files |
| Focused evaluation tests | 5 passed |
| Full test suite | 227 passed, 1 skipped |
| Real baseline evaluation | Exit 1 because `score_within_one_rate` is 0.6, below the 0.8 MVP gate |

## Changed Files

- `.gitignore`
- `src/warmai/evaluation/metrics.py`
- `src/warmai/evaluation/reporting.py`
- `src/warmai/evaluation/runner.py`
- `tests/integration/evaluation/test_reporting.py`
- `tests/unit/evaluation/test_runner.py`
- `docs/task-reports/2026-06-21-evaluation-baseline-and-failure-report.md`

Generated runtime artifacts:

- `reports/latest_failures.jsonl`
- `reports/history/20260621T083518Z-failures.jsonl`
- `reports/failures.md`

## Commit Information

No commit was created in this task.
