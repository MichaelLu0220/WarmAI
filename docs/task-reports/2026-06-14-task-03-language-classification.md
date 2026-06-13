# WarmAI Task 3 Completion Report

## Task

Classify Supported Input Languages.

## Scope

- Added deterministic `zh-TW`, `en`, and `mixed` input classification.
- Added NFKC normalization and whitespace trimming.
- Added Han and Latin script detection.
- Added rejection for blank, symbol-only, emoji-only, number-only,
  unsupported-script, replacement-character, and non-letter Latin-symbol
  inputs.
- Added deterministic primary-language selection for mixed input.
- Added focused unit tests for supported and rejected inputs.

No Task 4 or later functionality was implemented.

## Git Cleanup

Before Task 3, `main` was fast-forwarded to the approved Task 2 result.
The local `codex/warmai-task-1` and `codex/warmai-task-2` branches were
deleted. Task 3 was implemented directly on `main`, and `main` is the only
local branch.

## TDD Evidence

### Initial RED

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\text\test_language.py `
  -v -p no:cacheprovider `
  --basetemp=.pytest-basetemp-task3
```

Result:

```text
ModuleNotFoundError: No module named 'warmai.text'
```

The test failed for the expected missing-feature reason before production
code existed.

### Plan Contradiction

The plan's test requires:

```text
整理 README file -> mixed, primary zh-TW
Update 文件 -> mixed, primary en
```

The supplied count-based implementation returned `en` for the first example
because it counted more Latin characters than Han characters. The design
requires a primary language for mixed input but does not define count-based
semantics.

The minimal accepted resolution uses the first analyzable Han or Latin
character to determine the primary language. This satisfies both specified
acceptance cases without changing other classification behavior.

### Initial GREEN

After resolving the contradiction:

```text
Focused Task 3 tests: 9 passed
All unit tests: 15 passed
Ruff: passed
mypy: passed
```

## Quality Review Fix

The code-quality review found that Unicode names containing `LATIN` also
include non-letter symbols and combining marks. For example:

```text
U+271D LATIN CROSS
U+0363 COMBINING LATIN SMALL LETTER A
```

Both have `isalpha() == False` and must be rejected as unanalyzable rather
than classified as English.

### Regression RED

After adding the two regression cases:

```text
2 failed, 9 passed
U+271D: DID NOT RAISE LanguageClassificationError
U+0363: DID NOT RAISE LanguageClassificationError
```

### Regression GREEN

`_is_latin()` was minimally restricted to alphabetic characters whose
Unicode name contains `LATIN`.

```text
Focused Task 3 tests: 11 passed
All unit tests: 17 passed
Ruff: passed
mypy: passed
```

## Final Verification

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit `
  -v -p no:cacheprovider `
  --basetemp=.pytest-basetemp-task3-final
```

Result:

```text
17 passed in 0.43s
```

Additional checks:

| Check | Result |
| --- | --- |
| Ruff on Task 3 source and tests | Passed |
| mypy on `src/warmai/text/language.py` | No issues |
| Git diff check | Passed |
| Spec compliance review | Passed |
| Code quality re-review | Passed, no findings |
| Local branches | `main` only |
| Git worktree | Clean before report creation |

## Files Changed

- `src/warmai/text/language.py`
- `tests/unit/text/test_language.py`

## Commits

```text
8cc83a811939746612ce0d59758e865ed00a938b
feat: classify supported task languages

b0cefd22fd6d3438d676a024bd3a6fa1af19256e
fix: reject non-letter Latin symbols
```

Branch:

```text
main
```
