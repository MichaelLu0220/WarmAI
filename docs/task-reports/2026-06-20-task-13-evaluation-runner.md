# WarmAI Task 13 Completion Report

## Task

Build the Evaluation Runner and Fixed Reports.

Task 13 of 14.

## Scope

- Added evaluation case model, metrics, fixed report writer, and HTTP runner.
- Added deterministic report outputs:
  - `reports/latest.json`
  - `reports/history/<run_id>.json`
  - `reports/summary.md`
- Added MVP gate checks for score tolerance, valid JSON, language preservation,
  and p95 latency.
- Seeded `evaluation/core.jsonl` and `evaluation/hard_cases.jsonl`.
- Added `reports/history/.gitkeep`.
- Did not implement Task 14 release documentation.

## TDD Evidence

Initial RED:

```text
3 collection errors
ModuleNotFoundError: No module named 'warmai.evaluation'
```

Final GREEN:

```text
Focused Task 13 tests: 7 passed
Complete test suite: 223 passed, 1 skipped
```

## Final Verification

| Check | Result |
| --- | --- |
| Focused Task 13 tests | 7 passed in 0.72s |
| Complete test suite | 223 passed, 1 skipped in 6.63s |
| Ruff format | 8 files already formatted |
| Ruff lint | Passed |
| Task 13 mypy | No issues |
| Diff whitespace check | Passed |
| Spec review | Main-agent check passed; subagents skipped to conserve quota |
| Quality review | Main-agent check passed; subagents skipped to conserve quota |
| Branch | `main` only |

## Notes

- Full test runs emit the existing `StarletteDeprecationWarning` from
  `fastapi.testclient`/`httpx`; tests pass.
- The pre-existing `.pytest-basetemp-task4/` sandbox artifact remains untracked
  and is not part of Task 13.

## Files Changed

- `src/warmai/evaluation/__init__.py`
- `src/warmai/evaluation/cases.py`
- `src/warmai/evaluation/metrics.py`
- `src/warmai/evaluation/reporting.py`
- `src/warmai/evaluation/runner.py`
- `evaluation/core.jsonl`
- `evaluation/hard_cases.jsonl`
- `reports/history/.gitkeep`
- `tests/unit/evaluation/test_metrics.py`
- `tests/unit/evaluation/test_runner.py`
- `tests/integration/evaluation/test_reporting.py`

## Commits

```text
bd72d3b1379fb94795d418e8a61d24ebe5c1642a
feat: add reproducible evaluation runner
```
