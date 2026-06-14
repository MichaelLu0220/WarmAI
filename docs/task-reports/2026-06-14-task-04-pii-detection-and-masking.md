# WarmAI Task 4 Completion Report

## Task

Detect and Mask PII Before Persistence.

Task 4 of 14.

## Scope

- Added deterministic detection for email addresses, Taiwan mobile phone
  numbers, Taiwan national IDs, IPv4-shaped values, and contextual Chinese
  names.
- Added stable typed spans and deterministic placeholder masking.
- Added longest-span overlap resolution so enclosing email matches take
  precedence over phone or ID-shaped substrings.
- Added validation for overlapping, empty, reversed, negative, and
  out-of-range external spans.
- Added focused positive, negative, boundary, overlap, and exact-output
  regression tests.

No Task 5 or later functionality was implemented.

## TDD Evidence

### Initial RED

The first focused test failed before production code existed:

```text
ModuleNotFoundError: No module named 'warmai.privacy'
```

### Initial GREEN

```text
Focused Task 4 tests: 2 passed
All unit tests: 19 passed
Scoped mypy: passed
```

## First Quality Review

The first code-quality review found:

- Contextual names included trailing action characters.
- Overlapping email, phone, and ID matches could corrupt masked output.
- The phone expression accepted invalid domestic and international forms.
- Exact output and negative boundary coverage were insufficient.
- The full-width comma caused the default Ruff gate to fail.
- Same-kind placeholders were numbered right-to-left.

### Regression RED

```text
17 collected, 8 failed, 9 passed
```

### Regression GREEN

```text
Focused Task 4 tests: 17 passed
All unit tests: 34 passed
Ruff: passed
Scoped mypy: passed
```

## Second Quality Review

The second review found:

- Continued Chinese sentences could still leak contextual names.
- Common phrases such as `找時間` could be destructively misclassified.
- Underscore-delimited identifiers could contain a false-positive phone.
- Invalid external spans were not rejected.
- Additional overlap, Taiwan ID, and IPv4 regressions were missing.

### Regression RED

```text
33 collected, 14 failed, 19 passed
```

### Regression GREEN

```text
Focused Task 4 tests: 33 passed
All unit tests: 50 passed
Ruff: passed
Scoped mypy: passed
```

## Final Spec Correction

A surname allowlist introduced during the quality fix was too restrictive
for the plan's generic contextual-name requirement. It missed examples such
as `聯絡周杰倫`.

The allowlist was replaced with a narrow explicit set of known non-person
phrases. Exact regressions cover both `聯絡周杰倫` and
`提醒司馬懿明天開會`, while retaining the common-phrase negative cases.

## Final Verification

Results from the main implementation controller:

| Check | Result |
| --- | --- |
| Focused privacy tests | 35 passed in 0.14s |
| All unit tests | 52 passed in 0.57s |
| Ruff on `src` and `tests/unit` | Passed |
| mypy on `src/warmai/privacy` | No issues |
| Git diff check | Passed |
| Branch | `main` only |

The final reviewer follow-up messages were interrupted by the execution
environment after the earlier review cycles. The final two-case spec
correction was therefore inspected and verified by the main controller.

## Files Changed

- `src/warmai/privacy/pii.py`
- `src/warmai/privacy/masking.py`
- `tests/unit/privacy/test_masking.py`

## Commits

```text
651ee5d652107acfd5a5cbe7d0070b7537e0dd91
feat: mask PII before persistence

2bfa306494a0b765d063c068753edb6d0b7bb7aa
fix: harden PII detection and masking

66d3455ba2d042dc28e4309fad4ebfbe26b2dd2f
fix: tighten PII detection heuristics

05f5cc9
fix: preserve generic contextual name detection
```

The generated `.pytest-basetemp-task4/` directory remains untracked because
its sandbox-created symbolic link denies removal even with approved elevated
access. It contains only test-run artifacts and is not part of the product or
Task 4 deliverables.

Branch:

```text
main
```
