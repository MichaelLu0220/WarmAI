# WarmAI Task 6 Completion Report

## Task

Implement Deadline, Circuit Breaker, and Adapter Protocol.

Task 6 of 14.

## Scope

- Added a finite, monotonic shared `Deadline`.
- Added a closed/open/half-open circuit breaker with threshold, recovery,
  single-probe, permit identity, and stale-outcome protection.
- Added the adapter protocol, availability error, immutable response, and
  deterministic mock adapter.
- Added focused unit coverage without implementing Task 7 or later behavior.

## TDD Evidence

Initial RED:

```text
2 collection errors
ModuleNotFoundError: No module named 'warmai.inference'
```

Review-driven RED cycles covered:

- non-finite deadline and breaker values
- invalid state transitions and abandoned half-open probes
- stale, foreign, copied, denied, consumed, and replayed permits
- finite-value subtraction overflow

Final GREEN:

```text
Focused Task 6 tests: 84 passed
Complete test suite: 158 passed
```

## Final Verification

| Check | Result |
| --- | --- |
| Focused Task 6 tests | 84 passed in 0.17s |
| Complete test suite | 158 passed in 1.13s |
| Ruff format | 6 files formatted |
| Ruff lint | Passed |
| Task 6 mypy | No issues |
| Spec review | Compliant |
| Quality review | Approved |
| Branch | `main` only |

## Files Changed

- `src/warmai/inference/deadline.py`
- `src/warmai/inference/circuit_breaker.py`
- `src/warmai/inference/adapters/base.py`
- `src/warmai/inference/adapters/mock.py`
- `tests/unit/inference/test_deadline.py`
- `tests/unit/inference/test_circuit_breaker.py`

## Commits

```text
3b80436854910a404cb3cbf7129df98161a92164
feat: add inference control primitives

1891188e30c9fdd445d327976e04da8043c1fd09
fix: harden inference control invariants

27435e8a680bd207185e616741b6ed86c58ababf
fix: bind circuit outcomes to probe permits

9e14af9ed87e50f9e54eb8a6064499b82497ecd5
fix: complete circuit permit validation

6dca473dc165f64aecd944a033e33e7d55b48596
fix: consume exact circuit admission permits
```

The pre-existing `.pytest-basetemp-task4/` sandbox artifact remains
untracked and is not part of Task 6.
