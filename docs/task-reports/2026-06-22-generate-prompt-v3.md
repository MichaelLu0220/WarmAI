# Generate Prompt V3

## Scope

- Added optimizer support for an explicit candidate prompt version through `--candidate-prompt-version`.
- Added `--generate-only` so the agent can stop immediately after creating a candidate prompt without running evaluation or accepting/rejecting it.
- Ran the optimizer once to create `task-analysis-003.txt`.
- Switched `PROMPT_VERSION` to `task-analysis-003`.
- Updated the prompt loading test so it verifies the active `PROMPT_VERSION` instead of hard-coding the previous prompt version.

## TDD Evidence

- Added failing coverage for explicit candidate prompt version creation, then implemented the option.
- Added failing coverage for generate-only runner behavior, then implemented the option.
- Added failing coverage for candidate guidance placement before the task text, then updated prompt variant insertion.
- Re-ran the affected focused tests after implementation.

## Verification Results

- `uv run --extra dev python -m pytest tests\unit\inference\test_service.py::test_build_prompt_includes_version_language_task_and_retry_note -v -p no:cacheprovider`
  - Result: `1 passed`
- `uv run --extra dev ruff format --check .`
  - Result: `66 files already formatted`
- `uv run --extra dev ruff check .`
  - Result: `All checks passed!`
- `uv run --extra dev mypy src\warmai`
  - Result: `Success: no issues found in 40 source files`
- `uv run --extra dev python -m pytest tests\unit\evaluation -v -p no:cacheprovider`
  - Result: `33 passed`
- `uv run --extra dev python -m pytest -v -p no:cacheprovider`
  - Result: `258 passed, 1 skipped, 1 warning`

## Changed Files

- `src/warmai/evaluation/optimizer.py`
- `src/warmai/config/model_config.py`
- `src/warmai/inference/prompts/task-analysis-003.txt`
- `tests/unit/evaluation/test_optimizer.py`
- `tests/unit/inference/test_service.py`
- `docs/task-reports/2026-06-22-generate-prompt-v3.md`

## Commit Information

- Commit created: no.
- Reason: this workflow is using JSONL experiment logging and the user did not request a git commit.

## Notes

- The optimizer was run with `--generate-only`, so it wrote a `candidate_started` experiment event and intentionally did not run suite comparison or mark the candidate accepted/rejected.
- `reports/experiments/warmai-experiments.jsonl` remains an ignored local experiment log.
