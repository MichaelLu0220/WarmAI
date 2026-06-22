# Strict Flow Optimizer

## Scope

- Updated `warmai-optimize` so normal optimization runs cannot skip the WarmAI flow.
- Added dataset hash tracking to optimizer runs.
- Added baseline stability gating with 3 to 5 stability suite runs before candidate creation.
- Added a stop condition when the baseline is unstable, before any candidate prompt is created.
- Changed automatic prompt version generation from `task-analysis-auto-0001` to numeric progression from the active prompt version, such as `task-analysis-002` to `task-analysis-003`.
- Verified that after `task-analysis-003` is accepted, the next candidate generated after the new baseline stability gate is `task-analysis-004`.
- Kept manual candidate generation available only with the explicit `--allow-manual-candidate` override.
- Updated optimizer documentation to describe strict flow behavior.

## TDD Evidence

- Added failing tests for strict baseline plus stability runs before candidate creation.
- Added a failing test that an unstable baseline stops before candidate creation.
- Added a failing test that accepting `task-analysis-003` leads to `task-analysis-004` after the new baseline stability gate.
- Added a failing test that `--generate-only` requires explicit manual override.
- Added failing prompt-generator tests for numeric version progression.
- Implemented the minimal optimizer changes until those tests passed.

## Verification Results

- `uv run --extra dev python -m pytest tests\unit\evaluation\test_optimizer.py -v -p no:cacheprovider`
  - Red before implementation: `10 failed, 6 passed`
  - Green after implementation: `16 passed`
- `uv run --extra dev ruff format --check .`
  - Initial result: `Would reformat: src\warmai\evaluation\optimizer.py`
- `uv run --extra dev ruff format src\warmai\evaluation\optimizer.py tests\unit\evaluation\test_optimizer.py`
  - Result: `1 file reformatted, 1 file left unchanged`
- `uv run --extra dev ruff format --check .`
  - Result: `66 files already formatted`
- `uv run --extra dev ruff check .`
  - Result: `All checks passed!`
- `uv run --extra dev mypy src\warmai`
  - Result: `Success: no issues found in 40 source files`
- `uv run --extra dev python -m pytest tests\unit\evaluation -v -p no:cacheprovider`
  - Result: `37 passed`
- `uv run --extra dev python -m pytest -v -p no:cacheprovider`
  - Result: `262 passed, 1 skipped, 1 warning`

## Changed Files

- `src/warmai/evaluation/optimizer.py`
- `tests/unit/evaluation/test_optimizer.py`
- `docs/warmai-optimization-agent.md`
- `docs/task-reports/2026-06-22-strict-flow-optimizer.md`

## Commit Information

- Commit created: no.
- Reason: this workflow is using JSONL experiment logging and the user did not request a git commit.

## Notes

- Normal `warmai-optimize` runs now execute the baseline and stability gate before any candidate is created.
- `--generate-only` remains available only for manual inspection and requires `--allow-manual-candidate`; it is not the strict optimization loop.
