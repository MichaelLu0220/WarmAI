# WarmAI Optimization Agent

WarmAI optimization uses a constrained experiment loop. The agent records every
experiment in a local JSONL ledger and keeps Git for accepted code/config
milestones only.

## Local Experiment Ledger

The experiment ledger is:

```text
reports/experiments/warmai-experiments.jsonl
```

This path is ignored by Git. The ledger is append-only: every baseline creation,
stability run, candidate result, rejection, acceptance, standard change, and
batch commit marker is appended as one JSON object per line.

The agent must rebuild state by replaying the JSONL file, not from chat memory.
The rebuilt state includes:

```text
current_baseline_id
latest_candidate_id
accepted_since_last_commit
accepted_candidates
rejected_candidates
last_dataset_hash
```

## Commit Policy

Rejected candidates do not count toward the batch commit threshold.

Accepted candidates increase `accepted_since_last_commit` by 1. The agent may
prepare a batch commit only after the configured threshold is reached, usually 5
or 10 accepted candidates.

Dataset changes, gate changes, and evaluation-standard changes force a new
baseline, but they do not count as accepted candidates.

## Allowed Phases

The agent is not allowed to freely edit the codebase. Each phase has a narrow
file and factor allowlist.

### expand_dataset

Allowed paths:

```text
evaluation/*.jsonl
```

Allowed action: add or revise evaluation cases. After this phase, the dataset
hash changes and all baselines must be rebuilt.

### baseline_check

Allowed paths:

```text
none
```

Allowed action: run the evaluation suite 3 to 5 times and append stability
results. No source, prompt, config, dataset, or test file may be edited.

### stabilize

Allowed paths:

```text
src/warmai/config/model_config.py
runtime/server configuration documented outside Git
```

Allowed factors:

```text
temperature
top_p
top_k
timeout
MAX_OUTPUT_TOKENS
retry
```

Only one factor may change per round. `retry` requires explicit human approval
because the current project requirements document says `MAX_RETRY = 1` is a
fixed fallback boundary.

### prompt_candidate

Allowed paths:

```text
src/warmai/inference/prompts/*.txt
src/warmai/config/model_config.py
```

Allowed factor:

```text
prompt
```

The agent may add a prompt version and switch `PROMPT_VERSION`, but it may not
change unrelated inference or API behavior.

### rubric_candidate

Allowed paths:

```text
src/warmai/inference/prompts/*.txt
```

Allowed factor:

```text
scoring_rubric
```

The agent may revise scoring instructions inside the active candidate prompt,
but it must not change model configuration in the same round.

## Candidate Decision Rules

A candidate is rejected if JSON validity, HTTP contract pass rate, or language
preservation regresses.

A candidate can be accepted only when critical stability metrics do not regress
and the target metric improves enough to justify replacing the baseline.

When a candidate is rejected, the agent records the rejection in JSONL and
reverts only that candidate's changes.

When a candidate is accepted, the agent records the acceptance in JSONL and the
candidate becomes the new baseline. The accepted changes remain in the working
tree until the accepted-candidate batch threshold is reached.

## CLI

Show reconstructed state:

```powershell
warmai-experiment-log show-state
```

Record a candidate result:

```powershell
warmai-experiment-log record-candidate-result `
  --baseline-id baseline-a `
  --candidate-id candidate-a1 `
  --changed-factor prompt `
  --changed-file src/warmai/inference/prompts/task-analysis-003.txt `
  --suite-report reports/suite/latest.json `
  --decision accepted `
  --reason "Score improved with no contract regression."
```

Mark a batch commit as completed:

```powershell
warmai-experiment-log mark-batch-commit-done `
  --baseline-id baseline-f `
  --reason "Committed five accepted candidates."
```

## Optimization Runner

Run constrained prompt/rubric optimization rounds:

```powershell
warmai-optimize `
  --rounds 100 `
  --base-url http://127.0.0.1:8000 `
  --api-key dev-secret `
  --mode prompt `
  --accepted-threshold 5 `
  --stability-runs 3 `
  --reload-wait-seconds 1
```

`warmai-optimize` runs the WarmAI flow strictly. Before it creates a candidate,
it must:

```text
1. Fix the current usable version.
2. Check the evaluation dataset hash.
3. Run the first Evaluation Suite.
4. Record the current version as the baseline.
5. Run 3 to 5 stability suites for the same baseline.
6. Pass the stability gate.
7. Stop before candidate creation if the baseline is unstable.
```

Only after that gate passes may it enter the single-factor optimization loop
and create a prompt or rubric candidate.

Manual step-10-only candidate generation is available for inspection, but it is
not the normal optimization agent loop and requires an explicit override:

```powershell
warmai-optimize `
  --rounds 1 `
  --base-url http://127.0.0.1:8000 `
  --api-key dev-secret `
  --mode prompt `
  --candidate-prompt-version task-analysis-003 `
  --generate-only `
  --allow-manual-candidate
```

Modes:

```text
prompt
rubric
```

The runner creates candidate prompt versions such as:

```text
src/warmai/inference/prompts/task-analysis-003.txt
src/warmai/inference/prompts/task-analysis-004.txt
```

For prompt candidates, it also updates:

```text
src/warmai/config/model_config.py
```

The runner records each candidate result in:

```text
reports/experiments/warmai-experiments.jsonl
```

If a candidate is rejected, the runner restores the previous `PROMPT_VERSION`
and deletes the generated candidate prompt file. If a candidate is accepted,
the generated prompt and config change remain in the working tree.

When a numeric prompt version is active, the next generated prompt increments
that version. For example:

```text
task-analysis-002 -> task-analysis-003
task-analysis-003 -> task-analysis-004
```

If `task-analysis-003` is accepted, the candidate becomes the new baseline.
Before creating `task-analysis-004`, the runner goes back through the baseline
and stability gate for the new baseline.

When `accepted_since_last_commit` reaches `--accepted-threshold`, the runner
appends `batch_commit_ready` to the JSONL ledger. It does not create a Git
commit by itself.

### Server Reload Requirement

`warmai-optimize` evaluates through the configured WarmAI HTTP server. If the
server was started before the runner changed prompt/config files, it may still
use the old imported `PROMPT_VERSION`.

For prompt/rubric optimization, run WarmAI with reload or restart it between
candidate rounds. In local development, use a reload-capable server command so
the service picks up generated prompt versions before each suite run.
