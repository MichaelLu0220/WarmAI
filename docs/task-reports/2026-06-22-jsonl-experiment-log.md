# JSONL Experiment Log Completion Report

## Scope

- Added a local-only JSONL experiment ledger module for WarmAI optimization runs.
- Added replayable experiment state:
  - current baseline
  - latest candidate
  - accepted candidates
  - rejected candidates
  - accepted candidate count since the last batch commit
  - last dataset hash
- Added `warmai-experiment-log` CLI with:
  - `show-state`
  - `record-candidate-result`
  - `mark-batch-commit-done`
- Added suite-report metric extraction for candidate result events.
- Ignored local experiment logs and temporary workspace verification folders.
- Documented the constrained WarmAI optimization-agent loop and allowed phase edit boundaries.

## TDD Evidence

Initial RED for the log/state module:

```text
ModuleNotFoundError: No module named 'warmai.evaluation.experiment_log'
```

Focused GREEN for log/state:

```text
tests/unit/evaluation/test_experiment_log.py
4 passed in 0.43s
```

Initial RED for the CLI:

```text
ImportError: cannot import name 'main' from 'warmai.evaluation.experiment_log'
```

Focused GREEN for CLI:

```text
tests/unit/evaluation/test_experiment_log_cli.py
4 passed in 0.23s
```

## Verification Results

| Check | Result |
| --- | --- |
| Docs presence check | `Test-Path docs\warmai-optimization-agent.md` returned `True` |
| Ruff format | `64 files already formatted` |
| Ruff lint | Passed |
| Mypy | No issues in 39 source files |
| Focused evaluation tests | 21 passed |
| Full test suite | 246 passed, 1 skipped, 1 warning |

The skipped test is the opt-in real llama.cpp smoke test. The warning is the
existing `StarletteDeprecationWarning` from FastAPI/TestClient.

## Environment Note

The existing `.venv` could not start in this sandbox because its Python runtime
could not find the standard-library `encodings` module. Verification used a
workspace-local `.codex-venv` created through `uv run --extra dev` with
`TEMP`, `TMP`, `UV_CACHE_DIR`, and `UV_PROJECT_ENVIRONMENT` pointed inside the
workspace. These local verification paths are ignored by Git.

## Changed Files

- `.gitignore`
- `pyproject.toml`
- `src/warmai/evaluation/experiment_log.py`
- `tests/unit/evaluation/test_experiment_log.py`
- `tests/unit/evaluation/test_experiment_log_cli.py`
- `docs/warmai-optimization-agent.md`
- `docs/task-reports/2026-06-22-jsonl-experiment-log.md`

Ignored local planning artifact:

- `docs/superpowers/plans/2026-06-22-jsonl-experiment-log.md`

## Commit Information

No commit was created in this task. The experiment ledger is designed so future
optimization runs can record many iterations locally without adding experiment
history to Git.
