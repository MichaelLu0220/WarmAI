# WarmAI Task 5 Completion Report

## Task

Add SQLite Migrations and Repositories.

Task 5 of 14.

## Scope

- Added the initial SQLite schema for inference events, idempotency records,
  dataset candidates, teacher votes, and the model registry.
- Added an asynchronous database connection wrapper with parent-directory
  creation, WAL mode, foreign keys, busy timeout, and bounded lock retries.
- Added ordered, idempotent, concurrent-safe, and transactional migrations.
- Added migration script validation for malformed SQL, transaction-control
  statements, duplicate versions, missing directories, and UTF-8 BOM input.
- Added an inference event repository that stores and reconstructs masked
  payloads, booleans, and JSON string lists using explicit SQL columns.
- Added integration coverage for migration and repository behavior.

No Task 6 or later repository behavior was implemented.

## TDD Evidence

### Initial RED

```text
2 collection errors
ModuleNotFoundError: No module named 'warmai.persistence'
```

### Initial GREEN

```text
Focused persistence tests: 4 passed
Full test suite: 56 passed
Ruff: passed
Scoped mypy: passed
```

## First Quality Review

The first review found:

- Migration SQL could contain `COMMIT` or `ROLLBACK` and escape the runner's
  transaction.
- Concurrent migration runners could both read stale version state.
- A missing migration directory silently succeeded.
- The original privacy assertion did not inspect the schema boundary.

### Regression RED

```text
8 failed, 5 passed
```

### Regression GREEN

```text
Focused persistence tests: 13 passed
Full test suite: 65 passed
Ruff: passed
Scoped mypy: passed
Concurrent migration stress: 10 consecutive runs passed
```

## Second Quality Review

The second review found:

- A UTF-8 BOM caused the first SQL statement to be discarded.
- Unknown statement prefixes such as `@INVALID` were silently ignored.
- The concurrency regression did not deterministically force stale reads.
- WAL retry branches lacked committed coverage.

### Regression RED

```text
2 failed, 17 passed
```

### Regression GREEN

```text
Focused persistence tests: 20 passed
Full test suite: 72 passed
Ruff: passed
Scoped mypy: passed
```

The corrected parser accepts a leading BOM, preserves valid comments,
strings, and trigger bodies, and rejects unknown or incomplete SQL before
any migration statement is applied.

## Third Quality Review

The final review found:

- Extended SQLite lock codes such as `SQLITE_BUSY_RECOVERY` were not reduced
  to their primary result code before retry classification.
- The stale-read test wrapper did not preserve aiosqlite's awaitable
  async-context-manager protocol.

### Regression RED

```text
1 failed, 21 passed
```

### Regression GREEN

```text
Focused persistence tests: 22 passed
Full test suite: 74 passed
Ruff: passed
Scoped mypy: passed
```

## Final Verification

Results from the main implementation controller after formatting:

| Check | Result |
| --- | --- |
| Focused persistence tests | 22 passed in 0.74s |
| Complete test suite | 74 passed in 1.07s |
| Ruff format on Task 5 source/tests | Passed, 5 files formatted |
| Ruff lint on the repository | Passed |
| mypy on `src/warmai/persistence` | No issues |
| Git diff check | Passed |
| Spec compliance review | Passed |
| Code quality review | Approved |
| Branch | `main` only |

Residual quality note: repository-wide Ruff formatting still identifies two
pre-existing Task 3/4 files outside Task 5. They were intentionally left
unchanged to preserve single-task scope.

## Files Changed

- `migrations/001_initial.sql`
- `src/warmai/persistence/database.py`
- `src/warmai/persistence/migrations.py`
- `src/warmai/persistence/events.py`
- `tests/integration/persistence/test_migrations.py`
- `tests/integration/persistence/test_events.py`

## Commits

```text
44a561c7a4c427229c2bca1896b4832f0272c54a
feat: add SQLite persistence foundation

2ca29de2ac0e729ca62113eed1fea25c97ee7711
fix: harden SQLite migration transactions

8ec08693f42e4adad2c9d1777f0952c727264089
fix: validate SQLite migration scripts

31ddc02d0bf6025fcb9a0f436920d3d73de5b5f5
fix: handle extended SQLite lock codes

e2e741504f53261b1a51e22b3f888b3a9327fb85
style: format Task 5 persistence files
```

The pre-existing `.pytest-basetemp-task4/` sandbox artifact remains
untracked and unchanged. It is not part of Task 5.

Branch:

```text
main
```
