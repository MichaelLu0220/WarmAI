# WarmAI Hard Case Evaluation Completion Report

## Scope

- Extended `warmai-evaluate` to load both score cases and HTTP contract cases.
- Added `HttpEvaluationCase` for datasets such as `evaluation/hard_cases.jsonl`.
- Added `http_contract_pass_rate` to evaluation summaries and MVP gates.
- Kept score metrics scoped to score cases so hard cases do not distort score calibration.
- Extended failure reports with HTTP contract mismatch issues:
  - `expected_status_mismatch`
  - `expected_error_code_mismatch`
- Ran live evaluations for both `evaluation/core.jsonl` and `evaluation/hard_cases.jsonl`.

## TDD Evidence

Initial RED:

```text
8 failed, 4 passed

AttributeError: 'EvaluationSummary' object has no attribute 'http_contract_pass_rate'
TypeError: EvaluationSample.__init__() got an unexpected keyword argument 'case_type'
ValidationError: expected_http_status / expected_error_code extra inputs are not permitted
AttributeError: module 'warmai.evaluation.cases' has no attribute 'parse_case'
```

Focused GREEN:

```text
tests/unit/evaluation tests/integration/evaluation/test_reporting.py
12 passed in 0.73s
```

## Verification Results

| Check | Result |
| --- | --- |
| Ruff format | 59 files already formatted |
| Ruff lint | Passed |
| Mypy | No issues in 37 source files |
| Focused evaluation tests | 12 passed |
| Full test suite | 233 passed, 1 skipped, 1 warning |
| Live core evaluation | Exit 0; `score_within_one_rate: 1.0`, `http_contract_pass_rate: 1.0`, `p95_latency_ms: 4500` |
| Live hard-case evaluation | Exit 0; `http_contract_pass_rate: 1.0`, `p95_latency_ms: 3985`, no failing cases |

The full test suite still emits the existing `StarletteDeprecationWarning` from
FastAPI/TestClient.

## Changed Files

- `src/warmai/evaluation/cases.py`
- `src/warmai/evaluation/metrics.py`
- `src/warmai/evaluation/reporting.py`
- `src/warmai/evaluation/runner.py`
- `tests/integration/evaluation/test_reporting.py`
- `tests/unit/evaluation/test_metrics.py`
- `tests/unit/evaluation/test_runner.py`
- `docs/superpowers/plans/2026-06-21-hard-case-evaluation.md`
- `docs/task-reports/2026-06-21-hard-case-evaluation.md`

## Notes

- `reports/latest.json`, `reports/summary.md`, and failure report artifacts are runtime outputs and remain ignored.
- Existing prompt/config changes were present in the working tree and are not part of this evaluation-runner change.

## Commit Information

No commit was created in this task.
