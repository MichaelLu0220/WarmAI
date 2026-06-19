# WarmAI Task 8 Completion Report

## Task

Build the Versioned Prompt and Inference Service.

Task 8 of 14.

## Scope

- Added versioned prompt construction using `PROMPT_VERSION`.
- Added `InferenceService` and immutable `InferenceResult`.
- Orchestrated direct validation, syntax-only JSON repair, bounded retry,
  partial recovery, adapter availability fallback, circuit-open fallback, and
  safe default output.
- Serialized model requests with an async lock.
- Added focused unit coverage without implementing Task 9 or later behavior.

## TDD Evidence

Initial RED:

```text
1 collection error
ModuleNotFoundError: No module named 'warmai.inference.prompt'
```

Review-driven RED:

```text
1 failed, 8 passed
test_adapter_failure_that_opens_circuit_reports_adapter_error
expected validation_result 'backend unavailable', got 'circuit_open'
```

Final GREEN:

```text
Focused Task 8 tests: 9 passed
Complete test suite: 191 passed
```

## Final Verification

| Check | Result |
| --- | --- |
| Focused Task 8 tests | 9 passed in 0.28s |
| Complete test suite | 191 passed in 1.05s |
| Ruff format | 9 files already formatted |
| Ruff lint | Passed |
| Task 8 mypy | No issues |
| Diff whitespace check | Passed |
| Spec review | Main-agent check passed; subagents unavailable due usage limit |
| Quality review | Main-agent check passed; subagents unavailable due usage limit |
| Branch | `main` only |

## Files Changed

- `src/warmai/inference/prompt.py`
- `src/warmai/inference/service.py`
- `tests/unit/inference/test_service.py`

## Commits

```text
ca529fae118a20559cf2dc9afcca430fe0f47052
feat: orchestrate bounded task inference
```

The pre-existing `.pytest-basetemp-task4/` sandbox artifact remains untracked
and is not part of Task 8.
