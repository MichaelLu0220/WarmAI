# WarmDock to WarmAI Mock Integration Design

Date: 2026-06-20

## Goal

Connect WarmDock Desktop to the local WarmAI service in mock-adapter mode so
task setup can request AI-style task analysis through the real WarmAI HTTP
contract.

This validates product wiring before real-model work:

- WarmDock can call local WarmAI.
- WarmDock can map WarmAI JSON into its existing `AiAnalysis` shape.
- WarmDock remains usable when WarmAI is unavailable.
- The existing task detail flow keeps its current user experience.

## Non-Goals

- Do not connect Qwen3-4B or any real model.
- Do not train or fine-tune a model.
- Do not change the WarmAI API contract.
- Do not redesign the WarmDock task modal.
- Do not replace Supabase task persistence.

## Current State

WarmAI is complete as a local HTTP service:

```text
POST http://127.0.0.1:8000/v1/task-analysis
X-API-Key: dev-secret
```

WarmDock already has an `AiGateway` abstraction in `@warmdock/api`, but the
shared app/UI injection does not expose AI to the task modal. The task detail
modal currently computes difficulty suggestions locally with
`suggestDifficulty(title)`.

## Proposed Flow

```text
WarmDock Desktop
  -> TaskDetailModal
  -> @warmdock/app AI action
  -> local WarmAI gateway
  -> WarmAI /v1/task-analysis
  -> WarmAI mock adapter
  -> WarmDock AiAnalysis
  -> existing difficulty suggestion UI
```

## Components

### Local WarmAI Gateway

Add a browser/Tauri-safe gateway in `@warmdock/api` that implements the existing
`AiGateway` interface.

Configuration:

- `baseUrl`: default `http://127.0.0.1:8000`
- `apiKey`: default development value `dev-secret`
- `timeoutMs`: default `5000`

Request:

```json
{
  "text": "Clean the desk",
  "client_request_id": "<uuid>"
}
```

Headers:

```text
X-API-Key: <apiKey>
Idempotency-Key: <same uuid>
```

Response mapping:

```text
WarmAI result.suggested_text -> AiAnalysis.suggestedCorrection
WarmAI result.score          -> AiAnalysis.suggestedScore
WarmAI result.score          -> AiAnalysis.suggestedBand
WarmAI result.reason         -> AiAnalysis.reason
WarmAI status ok/degraded    -> AiAnalysis.available = true
```

Score-to-band mapping:

```text
1-2 -> easy
3   -> medium
4-5 -> hard
```

### App Gateway Injection

Extend WarmDock's UI gateway configuration to include optional `ai`.

If no AI gateway is configured, app code uses the current local
`suggestDifficulty(title)` fallback.

### Task Detail Modal

The modal should:

- Start with the current deterministic local suggestion immediately.
- Request WarmAI analysis after the title is available.
- Replace the suggestion and selected score when WarmAI returns successfully.
- Keep the current local suggestion if WarmAI fails.
- Never block confirming a task because AI is unavailable.

The existing modal layout stays intact.

## Error Handling

WarmAI failures are non-fatal:

- Connection refused
- Timeout
- HTTP non-2xx
- Invalid JSON
- Missing expected fields

All failures return or preserve the current local fallback:

```text
suggestedBand: suggestDifficulty(title)
suggestedScore: default score for that band
available: false
```

## Desktop Development Setup

Start WarmAI:

```powershell
cd G:\Micp\WarmAI
$env:WARMAI_API_KEY="dev-secret"
$env:WARMAI_ADAPTER_KIND="mock"
.\.venv\Scripts\python.exe -m uvicorn warmai.main:app --host 127.0.0.1 --port 8000
```

Start WarmDock Desktop separately. The first integration pass targets desktop
local development only.

## Testing

Add tests for:

- WarmAI response maps to `AiAnalysis`.
- WarmAI unavailable returns fallback and does not throw.
- Task modal can render while AI analysis is pending.
- Task modal still confirms with local fallback if AI fails.

Manual verification:

- Start WarmAI mock server.
- Start WarmDock Desktop.
- Create a draft task.
- Confirm the task detail modal receives a WarmAI-backed suggestion.
- Stop WarmAI and confirm WarmDock still works with fallback.

## Acceptance Criteria

- WarmDock Desktop can call WarmAI mock service at `127.0.0.1:8000`.
- WarmDock can create and set up a task even when WarmAI is down.
- No real-model configuration is required.
- Existing WarmDock tests pass.
- WarmAI is unchanged.
