# Optimization Agent Runner Completion Report

## Scope

- Added `warmai-optimize` as the first constrained WarmAI optimization runner.
- Added prompt/rubric candidate generation:
  - copies the active prompt into `task-analysis-auto-000N.txt`
  - appends one prompt/rubric variant per round
  - updates `PROMPT_VERSION` in `src/warmai/config/model_config.py`
- Added candidate restoration for rejected rounds:
  - restores the original model config
  - deletes the generated prompt candidate
- Added candidate decision logic:
  - rejects suite failures
  - rejects critical JSON/language/HTTP contract regressions
  - accepts score accuracy improvements
  - accepts lower unnecessary correction when score is equal
  - accepts latency improvement only when quality is otherwise equal
- Added optimizer loop behavior:
  - creates an initial baseline when the JSONL ledger has none
  - records candidate results in the local JSONL experiment log
  - writes `batch_commit_ready` when the accepted-candidate threshold is reached
- Added `warmai-optimize` to project scripts.
- Updated the optimization-agent documentation with runner usage and server reload caveat.

## TDD Evidence

Initial RED:

```text
ModuleNotFoundError: No module named 'warmai.evaluation.optimizer'
```

Focused GREEN:

```text
tests/unit/evaluation/test_optimizer.py
10 passed in 1.07s
```

Focused evaluation GREEN:

```text
tests/unit/evaluation
31 passed in 1.09s
```

## Verification Results

| Check | Result |
| --- | --- |
| Ruff format | 66 files already formatted |
| Ruff lint | Passed |
| Console script help | `warmai-optimize --help` exited 0 |
| Mypy | No issues in 40 source files |
| Focused optimizer tests | 10 passed |
| Focused evaluation tests | 31 passed |
| Full test suite | 256 passed, 1 skipped, 1 warning |

The skipped test is the opt-in real llama.cpp smoke test. The warning is the
existing `StarletteDeprecationWarning` from FastAPI/TestClient.

## Operation Note

`warmai-optimize` evaluates candidates through the configured WarmAI HTTP
server. For prompt/rubric candidates, run WarmAI with reload or restart the
server between candidate changes so the service imports the generated
`PROMPT_VERSION` before each suite run.

## Changed Files

- `pyproject.toml`
- `src/warmai/evaluation/optimizer.py`
- `tests/unit/evaluation/test_optimizer.py`
- `docs/warmai-optimization-agent.md`
- `docs/task-reports/2026-06-22-optimization-agent-runner.md`

Ignored local planning artifact:

- `docs/superpowers/plans/2026-06-22-optimization-agent-runner.md`

## Commit Information

No commit was created in this task.
