# WarmAI Task 14 Completion Report

## Task

Complete smoke coverage, MVP documentation, and full verification.

Task 14 of 14.

## Scope

- Added service startup smoke coverage for migration, request handling, fallback,
  and circuit breaker open behavior.
- Replaced the README with MVP scope, WSL2 setup, mock adapter run steps,
  llama.cpp Qwen3-4B run steps, verification commands, evaluation command, and
  privacy notes.
- Ran full formatting, lint, type, smoke, unit/integration, mock E2E, and
  privacy persistence checks.
- Did not run the opt-in real llama.cpp smoke test because no local
  llama.cpp/Qwen3-4B server was available in this environment.

## TDD Evidence

RED:

```text
tests/smoke/test_service_startup.py did not exist before Task 14.
Initial targeted smoke run after adding the tests exercised the new startup and
circuit-breaker requirements.
```

GREEN:

```text
tests/smoke/test_service_startup.py: 2 passed, 1 warning
Complete test suite: 225 passed, 1 skipped, 1 warning
```

## Final Verification

| Check | Result |
| --- | --- |
| Ruff format | `58 files already formatted` |
| Ruff lint | `All checks passed!` |
| Mypy | `Success: no issues found in 36 source files` |
| Focused smoke tests | `2 passed, 1 warning in 2.50s` |
| Complete test suite | `225 passed, 1 skipped, 1 warning in 5.96s` |
| Mock CLI E2E | Exit 0; returned WarmDock `schema_version: 1.0` response |
| Mock evaluation E2E | Exit 0; `score_within_one_rate: 1.0`, `valid_json_rate: 1.0`, `language_preservation_rate: 1.0`, `fallback_rate: 0.0`, `p95_latency_ms: 30` |
| Privacy persistence inspection | `PRIVACY_OK=1`; email masked as `[EMAIL_001]`, `pii_detected=1`, `training_eligible=0` |
| Real model smoke | Skipped by design; `tests/smoke/test_real_adapter.py` remains opt-in |
| Branch | Local `main` only |

## Notes

- Full test runs still emit the existing `StarletteDeprecationWarning` from
  `fastapi.testclient`/`httpx`; tests pass.
- Mock E2E generated `reports/latest.json`, `reports/summary.md`, and
  `reports/history/*.json`; these runtime outputs were removed before commit.
- The pre-existing `.pytest-basetemp-task4/` sandbox artifact remains untracked
  and is not part of Task 14.

## Files Changed

- `README.md`
- `src/warmai/text/language.py`
- `tests/smoke/test_service_startup.py`
- `docs/task-reports/2026-06-20-task-14-smoke-docs-full-verification.md`

## Commits

```text
adf34b6b75bae4298d7fbf20cba48b38812ddcf6
test: add MVP smoke coverage and runbook
```

Report commit message:

```text
docs: add Task 14 completion report
```
