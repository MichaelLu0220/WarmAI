# WarmAI Evaluation Suite Runner Completion Report

## Scope

- Added `warmai.evaluation.suite` as the suite orchestration module.
- Added `warmai-evaluate-suite` to `pyproject.toml` project scripts.
- The suite runner evaluates:
  - `evaluation/core.jsonl`
  - `evaluation/hard_cases.jsonl`
- Added suite outputs under `reports/suite/`:
  - `latest.json`
  - `summary.md`
  - `failures.md`
  - `history/<run_id>.json`
- Added `reports/suite/` to `.gitignore`.
- Reused existing single-dataset runner and reporting failure semantics.
- Added `unexpected_error_response` for HTTP cases that expect 200 but receive
  an error body.

## TDD Evidence

Initial RED:

```text
tests/unit/evaluation/test_suite.py
ModuleNotFoundError: No module named 'warmai.evaluation.suite'
```

Focused GREEN:

```text
tests/unit/evaluation/test_suite.py
4 passed in 0.79s
```

Final focused evaluation GREEN:

```text
tests/unit/evaluation tests/integration/evaluation/test_reporting.py
17 passed in 0.86s
```

## Verification Results

| Check | Result |
| --- | --- |
| Ruff format | 61 files already formatted |
| Ruff lint | Passed |
| Mypy | No issues in 38 source files |
| Focused evaluation tests | 17 passed |
| Full test suite | 238 passed, 1 skipped, 1 warning |
| Live suite via module | Exit 0; `overall_passed: true` |

The full test suite still emits the existing `StarletteDeprecationWarning` from
FastAPI/TestClient.

## Live Suite Result

```text
core:
  passed: true
  score_within_one_rate: 1.0
  http_contract_pass_rate: 1.0
  p95_latency_ms: 2500

hard_cases:
  passed: true
  score_within_one_rate: 1.0
  http_contract_pass_rate: 1.0
  p95_latency_ms: 4485

overall_passed: true
failures: none
```

Generated report:

- `reports/suite/latest.json`
- `reports/suite/summary.md`
- `reports/suite/failures.md`

## Environment Note

`warmai-evaluate-suite` is registered in `pyproject.toml`, but the current `.venv`
did not yet contain the generated `.exe` entry point. Refreshing the editable
install with `pip install -e . --no-deps` failed because the sandbox could not
fetch `hatchling`; `--no-build-isolation` also failed because `hatchling` is not
installed in the venv. The implementation was verified with:

```powershell
.\.venv\Scripts\python.exe -m warmai.evaluation.suite --base-url http://127.0.0.1:8000 --api-key dev-secret
```

After `uv sync --extra dev` in an environment with the lock/cache available, the
console script should be generated as `.\.venv\Scripts\warmai-evaluate-suite.exe`.

## Changed Files

- `.gitignore`
- `pyproject.toml`
- `src/warmai/evaluation/reporting.py`
- `src/warmai/evaluation/suite.py`
- `tests/unit/evaluation/test_suite.py`
- `tests/integration/evaluation/test_reporting.py`
- `docs/superpowers/plans/2026-06-21-evaluation-suite-runner.md`
- `docs/task-reports/2026-06-21-evaluation-suite-runner.md`

## Commit Information

Planned commit message: `feat: add evaluation suite runner`
