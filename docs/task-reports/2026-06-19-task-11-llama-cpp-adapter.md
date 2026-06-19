# WarmAI Task 11 Completion Report

## Task

Add the llama.cpp Adapter and Real-Model Smoke Test.

Task 11 of 14.

## Scope

- Added `LlamaCppAdapter` for llama.cpp OpenAI-compatible chat completions.
- Requested schema-constrained, non-streaming JSON output with thinking disabled.
- Added adapter error wrapping and `/v1/models` healthcheck.
- Added `build_adapter(settings)` so the app factory selects mock or llama.cpp
  from settings.
- Added an opt-in real-model smoke test guarded by
  `WARMAI_RUN_REAL_MODEL_SMOKE=1`.
- Did not implement Task 12 CLI behavior.

## TDD Evidence

Initial RED:

```text
3 collection errors
ModuleNotFoundError: No module named 'warmai.inference.adapters.llama_cpp'
ImportError: cannot import name 'build_adapter' from 'warmai.api.app'
```

Final GREEN:

```text
Focused Task 11 tests: 7 passed, 1 skipped
Complete test suite: 211 passed, 1 skipped
```

## Final Verification

| Check | Result |
| --- | --- |
| Focused Task 11 tests | 7 passed, 1 skipped in 1.02s |
| Complete test suite | 211 passed, 1 skipped in 2.65s |
| Ruff format | 12 files already formatted |
| Ruff lint | Passed |
| Task 11 mypy | No issues |
| Diff whitespace check | Passed |
| Spec review | Main-agent check passed; subagents skipped to conserve quota |
| Quality review | Main-agent check passed; subagents skipped to conserve quota |
| Branch | `main` only |

## Notes

- The real llama.cpp smoke test is present but skipped unless
  `WARMAI_RUN_REAL_MODEL_SMOKE=1` is set and a llama.cpp server is running.
- Full test runs emit the existing `StarletteDeprecationWarning` from
  `fastapi.testclient`/`httpx`; tests pass.
- The pre-existing `.pytest-basetemp-task4/` sandbox artifact remains untracked
  and is not part of Task 11.

## Files Changed

- `src/warmai/inference/adapters/llama_cpp.py`
- `src/warmai/api/app.py`
- `tests/unit/inference/adapters/test_llama_cpp.py`
- `tests/unit/api/test_app.py`
- `tests/smoke/test_real_adapter.py`

## Commits

```text
4b38e938c3c62159632d3eba1223ea5b9f274f20
feat: add llama.cpp inference adapter
```
