# WarmDock WarmAI Mock Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect WarmDock Desktop task setup to the local WarmAI mock HTTP service while preserving the existing local fallback behavior.

**Architecture:** `@warmdock/api` gets a local WarmAI `AiGateway` implementation that speaks the WarmAI `/v1/task-analysis` contract. `@warmdock/app` exposes optional AI gateway injection and a safe `analyzeTaskProposal` action. WarmDock Desktop wires the local gateway, and `TaskDetailModal` consumes the action without blocking task setup.

**Tech Stack:** TypeScript, React 19, Vite/Tauri, pnpm workspaces, Vitest, WarmAI FastAPI mock adapter.

---

## Execution Rules

- Execute one task at a time.
- Use TDD for every behavior change: write failing test, verify failure, implement, verify pass.
- After each task, create a Markdown completion report under `G:\Micp\WarmDock\docs\task-reports\`.
- Stop after each task and report test results, changed files, commit message, and report path.
- Do not connect a real model, train a model, or change the WarmAI API.

## File Map

```text
G:/Micp/WarmDock/packages/api/src/warmai.ts
  Local WarmAI HTTP gateway and score-to-band mapping.

G:/Micp/WarmDock/packages/api/src/warmai.test.ts
  Gateway request, response mapping, and fallback tests.

G:/Micp/WarmDock/packages/api/src/index.ts
  Exports the local WarmAI gateway.

G:/Micp/WarmDock/packages/app/src/client.ts
  Adds optional ai gateway injection.

G:/Micp/WarmDock/packages/app/src/orchestrators/ai.ts
  Safe app-level task analysis action with local fallback.

G:/Micp/WarmDock/packages/app/src/orchestrators/ai.test.ts
  Tests missing gateway, gateway success, and gateway failure behavior.

G:/Micp/WarmDock/packages/app/src/index.ts
  Exports the AI action.

G:/Micp/WarmDock/apps/desktop/src/lib/warmaiConfig.ts
  Reads desktop WarmAI local config from Vite env.

G:/Micp/WarmDock/apps/desktop/src/lib/warmaiConfig.test.ts
  Tests default and overridden desktop WarmAI config.

G:/Micp/WarmDock/apps/desktop/src/lib/client.ts
  Passes the local WarmAI gateway into the WarmDock client.

G:/Micp/WarmDock/packages/ui-web/src/ui/task/aiSuggestion.ts
  Pure helper for deriving modal suggestion state from local fallback plus AI result.

G:/Micp/WarmDock/packages/ui-web/src/ui/task/aiSuggestion.test.ts
  Tests pending, successful, and unavailable AI suggestion states.

G:/Micp/WarmDock/packages/ui-web/src/ui/task/TaskDetailModal.tsx
  Calls the app AI action and updates the existing suggestion UI.
```

## Task 1: Add Local WarmAI Gateway in `@warmdock/api`

**Files:**
- Create: `G:/Micp/WarmDock/packages/api/src/warmai.ts`
- Create: `G:/Micp/WarmDock/packages/api/src/warmai.test.ts`
- Modify: `G:/Micp/WarmDock/packages/api/src/index.ts`
- Create report: `G:/Micp/WarmDock/docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-01-api-gateway.md`

- [ ] **Step 1: Write the failing gateway tests**

Create `packages/api/src/warmai.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { createLocalWarmAiGateway, scoreToBand } from "./warmai";

describe("scoreToBand", () => {
  it("maps WarmAI scores to WarmDock bands", () => {
    expect(scoreToBand(1)).toBe("easy");
    expect(scoreToBand(2)).toBe("easy");
    expect(scoreToBand(3)).toBe("medium");
    expect(scoreToBand(4)).toBe("hard");
    expect(scoreToBand(5)).toBe("hard");
  });
});

describe("createLocalWarmAiGateway", () => {
  it("posts to WarmAI and maps a valid response", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetcher: typeof fetch = async (input, init) => {
      calls.push({ input, init });
      return new Response(
        JSON.stringify({
          status: "ok",
          result: {
            suggested_text: "Clean the desk",
            score: 2,
            reason: "Mock analysis.",
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      );
    };

    const gateway = createLocalWarmAiGateway({
      baseUrl: "http://127.0.0.1:8000",
      apiKey: "dev-secret",
      fetcher,
      requestIdFactory: () => "123e4567-e89b-42d3-a456-426614174000",
    });

    const analysis = await gateway.analyzeTaskProposal("Clena the desk");

    expect(analysis).toEqual({
      originalText: "Clena the desk",
      suggestedCorrection: "Clean the desk",
      suggestedBand: "easy",
      suggestedScore: 2,
      reason: "Mock analysis.",
      available: true,
    });
    expect(String(calls[0].input)).toBe("http://127.0.0.1:8000/v1/task-analysis");
    expect(calls[0].init?.headers).toMatchObject({
      "Content-Type": "application/json",
      "X-API-Key": "dev-secret",
      "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174000",
    });
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      text: "Clena the desk",
      client_request_id: "123e4567-e89b-42d3-a456-426614174000",
    });
  });

  it("returns a medium fallback when WarmAI is unavailable", async () => {
    const fetcher: typeof fetch = async () => {
      throw new TypeError("connection refused");
    };
    const gateway = createLocalWarmAiGateway({ fetcher });

    await expect(gateway.analyzeTaskProposal("Write report")).resolves.toEqual({
      originalText: "Write report",
      suggestedCorrection: null,
      suggestedBand: "medium",
      suggestedScore: 3,
      reason: "WarmAI analysis is unavailable; you can still confirm this task.",
      available: false,
    });
  });
});
```

- [ ] **Step 2: Run the test to verify RED**

Run from `G:/Micp/WarmDock`:

```powershell
pnpm --filter @warmdock/api exec vitest run src/warmai.test.ts
```

Expected: FAIL with module resolution error for `./warmai`.

- [ ] **Step 3: Implement the gateway**

Create `packages/api/src/warmai.ts`:

```ts
import type { Difficulty, DifficultyBand } from "@warmdock/core";
import type { AiGateway } from "./ports";
import type { AiAnalysis } from "./types";

interface WarmAiResponse {
  status?: string;
  result?: {
    suggested_text?: string | null;
    score?: number;
    reason?: string;
  };
}

export interface LocalWarmAiGatewayConfig {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
  fetcher?: typeof fetch;
  requestIdFactory?: () => string;
}

export function scoreToBand(score: Difficulty): DifficultyBand {
  if (score <= 2) return "easy";
  if (score === 3) return "medium";
  return "hard";
}

function fallback(title: string): AiAnalysis {
  return {
    originalText: title,
    suggestedCorrection: null,
    suggestedBand: "medium",
    suggestedScore: 3,
    reason: "WarmAI analysis is unavailable; you can still confirm this task.",
    available: false,
  };
}

function isDifficulty(score: number | undefined): score is Difficulty {
  return score === 1 || score === 2 || score === 3 || score === 4 || score === 5;
}

export function createLocalWarmAiGateway(config: LocalWarmAiGatewayConfig = {}): AiGateway {
  const baseUrl = config.baseUrl ?? "http://127.0.0.1:8000";
  const apiKey = config.apiKey ?? "dev-secret";
  const timeoutMs = config.timeoutMs ?? 5000;
  const fetcher = config.fetcher ?? fetch;
  const requestIdFactory = config.requestIdFactory ?? (() => crypto.randomUUID());

  return {
    async analyzeTaskProposal(title) {
      const requestId = requestIdFactory();
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const response = await fetcher(`${baseUrl.replace(/\/$/, "")}/v1/task-analysis`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": apiKey,
            "Idempotency-Key": requestId,
          },
          body: JSON.stringify({ text: title, client_request_id: requestId }),
          signal: controller.signal,
        });
        if (!response.ok) return fallback(title);

        const body = (await response.json()) as WarmAiResponse;
        const score = body.result?.score;
        if (!body.result || !isDifficulty(score)) return fallback(title);
        if (body.status !== "ok" && body.status !== "degraded") return fallback(title);

        return {
          originalText: title,
          suggestedCorrection: body.result.suggested_text ?? null,
          suggestedBand: scoreToBand(score),
          suggestedScore: score,
          reason: body.result.reason ?? "",
          available: true,
        };
      } catch {
        return fallback(title);
      } finally {
        clearTimeout(timeout);
      }
    },
  };
}
```

Modify `packages/api/src/index.ts`:

```ts
export * from "./types";
export * from "./ports";
export * from "./errors";
export * from "./client";
export * from "./warmai";
```

- [ ] **Step 4: Run GREEN verification**

Run:

```powershell
pnpm --filter @warmdock/api exec vitest run src/warmai.test.ts
pnpm --filter @warmdock/api typecheck
```

Expected: tests pass and typecheck exits 0.

- [ ] **Step 5: Add Task 1 report**

Create `docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-01-api-gateway.md` with scope, RED/GREEN evidence, verification commands, changed files, and commit message.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add packages/api/src/warmai.ts packages/api/src/warmai.test.ts packages/api/src/index.ts docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-01-api-gateway.md
git commit -m "feat: add local WarmAI gateway"
```

## Task 2: Expose Safe AI Analysis in `@warmdock/app`

**Files:**
- Modify: `G:/Micp/WarmDock/packages/app/package.json`
- Modify: `G:/Micp/WarmDock/pnpm-lock.yaml`
- Modify: `G:/Micp/WarmDock/packages/app/src/client.ts`
- Create: `G:/Micp/WarmDock/packages/app/src/orchestrators/ai.ts`
- Create: `G:/Micp/WarmDock/packages/app/src/orchestrators/ai.test.ts`
- Modify: `G:/Micp/WarmDock/packages/app/src/index.ts`
- Create report: `G:/Micp/WarmDock/docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-02-app-ai-action.md`

- [ ] **Step 1: Add the failing app orchestrator test**

Create `packages/app/src/orchestrators/ai.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { UiGateways } from "../client";
import { configureGateways } from "../client";
import { analyzeTaskProposal } from "./ai";

const baseGateways: Omit<UiGateways, "ai"> = {
  task: {} as UiGateways["task"],
  session: {} as UiGateways["session"],
  unlock: {} as UiGateways["unlock"],
  settings: {} as UiGateways["settings"],
};

describe("analyzeTaskProposal", () => {
  it("uses local fallback when no ai gateway is configured", async () => {
    configureGateways(baseGateways);

    await expect(analyzeTaskProposal("deploy production")).resolves.toMatchObject({
      originalText: "deploy production",
      suggestedBand: "hard",
      suggestedScore: 4,
      available: false,
    });
  });

  it("returns the configured ai gateway result", async () => {
    configureGateways({
      ...baseGateways,
      ai: {
        async analyzeTaskProposal(title) {
          return {
            originalText: title,
            suggestedCorrection: "Clean the desk",
            suggestedBand: "easy",
            suggestedScore: 2,
            reason: "Mock analysis.",
            available: true,
          };
        },
      },
    });

    await expect(analyzeTaskProposal("Clena the desk")).resolves.toMatchObject({
      suggestedCorrection: "Clean the desk",
      suggestedBand: "easy",
      suggestedScore: 2,
      available: true,
    });
  });

  it("falls back when the configured ai gateway throws", async () => {
    configureGateways({
      ...baseGateways,
      ai: {
        async analyzeTaskProposal() {
          throw new Error("WarmAI down");
        },
      },
    });

    await expect(analyzeTaskProposal("reply to email")).resolves.toMatchObject({
      suggestedBand: "easy",
      suggestedScore: 2,
      available: false,
    });
  });
});
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
pnpm --filter @warmdock/app exec vitest run src/orchestrators/ai.test.ts
```

Expected: FAIL because `vitest` or `./ai` is unavailable.

- [ ] **Step 3: Add Vitest to the app package**

Modify `packages/app/package.json`:

```json
{
  "name": "@warmdock/app",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "exports": {
    ".": "./src/index.ts"
  },
  "scripts": {
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "peerDependencies": {
    "react": "^19"
  },
  "dependencies": {
    "@warmdock/api": "workspace:*",
    "@warmdock/core": "workspace:*",
    "zustand": "^5.0.12"
  },
  "devDependencies": {
    "@types/react": "^19.1.8",
    "react": "^19.1.0",
    "typescript": "~5.8.3",
    "vitest": "^4.1.8"
  }
}
```

Run:

```powershell
pnpm install
```

Expected: `pnpm-lock.yaml` updates if needed.

- [ ] **Step 4: Implement optional AI injection and safe action**

Modify `packages/app/src/client.ts`:

```ts
import type {
  AiGateway,
  RealtimeGateway,
  SessionGateway,
  SettingsGateway,
  TaskGateway,
  UnlockGateway,
} from "@warmdock/api";

export interface UiGateways {
  task: TaskGateway;
  session: SessionGateway;
  unlock: UnlockGateway;
  settings: SettingsGateway;
  ai?: AiGateway;
  /** optional ??the demo (offline fake data) has no realtime. */
  realtime?: RealtimeGateway;
}
```

Create `packages/app/src/orchestrators/ai.ts`:

```ts
import type { AiAnalysis } from "@warmdock/api";
import { getDefaultScoreForBand, suggestDifficulty } from "@warmdock/core/rules/task";
import { getGateways } from "../client";

function fallback(title: string): AiAnalysis {
  const suggestedBand = suggestDifficulty(title);
  return {
    originalText: title,
    suggestedCorrection: null,
    suggestedBand,
    suggestedScore: getDefaultScoreForBand(suggestedBand),
    reason: "AI analysis is unavailable; you can still confirm this task.",
    available: false,
  };
}

export async function analyzeTaskProposal(title: string): Promise<AiAnalysis> {
  const ai = getGateways().ai;
  if (!ai) return fallback(title);

  try {
    return await ai.analyzeTaskProposal(title);
  } catch {
    return fallback(title);
  }
}
```

Modify `packages/app/src/index.ts` to export:

```ts
export { analyzeTaskProposal } from "./orchestrators/ai";
```

- [ ] **Step 5: Run GREEN verification**

Run:

```powershell
pnpm --filter @warmdock/app exec vitest run src/orchestrators/ai.test.ts
pnpm --filter @warmdock/app typecheck
```

Expected: tests pass and typecheck exits 0.

- [ ] **Step 6: Add Task 2 report**

Create `docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-02-app-ai-action.md` with scope, RED/GREEN evidence, verification commands, changed files, and commit message.

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add packages/app/package.json pnpm-lock.yaml packages/app/src/client.ts packages/app/src/orchestrators/ai.ts packages/app/src/orchestrators/ai.test.ts packages/app/src/index.ts docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-02-app-ai-action.md
git commit -m "feat: expose safe task AI analysis"
```

## Task 3: Wire WarmAI Into WarmDock Desktop

**Files:**
- Create: `G:/Micp/WarmDock/apps/desktop/src/lib/warmaiConfig.ts`
- Create: `G:/Micp/WarmDock/apps/desktop/src/lib/warmaiConfig.test.ts`
- Modify: `G:/Micp/WarmDock/apps/desktop/src/lib/client.ts`
- Create report: `G:/Micp/WarmDock/docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-03-desktop-wiring.md`

- [ ] **Step 1: Write the failing desktop config tests**

Create `apps/desktop/src/lib/warmaiConfig.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { warmAiConfigFromEnv } from "./warmaiConfig";

describe("warmAiConfigFromEnv", () => {
  it("uses local development defaults", () => {
    expect(warmAiConfigFromEnv({})).toEqual({
      baseUrl: "http://127.0.0.1:8000",
      apiKey: "dev-secret",
      timeoutMs: 5000,
    });
  });

  it("uses Vite environment overrides", () => {
    expect(
      warmAiConfigFromEnv({
        VITE_WARMAI_BASE_URL: "http://localhost:9000",
        VITE_WARMAI_API_KEY: "local-key",
        VITE_WARMAI_TIMEOUT_MS: "2500",
      })
    ).toEqual({
      baseUrl: "http://localhost:9000",
      apiKey: "local-key",
      timeoutMs: 2500,
    });
  });
});
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
pnpm --filter @warmdock/desktop exec vitest run src/lib/warmaiConfig.test.ts
```

Expected: FAIL because `./warmaiConfig` does not exist.

- [ ] **Step 3: Implement desktop WarmAI config**

Create `apps/desktop/src/lib/warmaiConfig.ts`:

```ts
import type { LocalWarmAiGatewayConfig } from "@warmdock/api";

export function warmAiConfigFromEnv(
  env: Record<string, string | undefined>
): Required<Pick<LocalWarmAiGatewayConfig, "baseUrl" | "apiKey" | "timeoutMs">> {
  const timeout = Number(env.VITE_WARMAI_TIMEOUT_MS ?? "5000");
  return {
    baseUrl: env.VITE_WARMAI_BASE_URL ?? "http://127.0.0.1:8000",
    apiKey: env.VITE_WARMAI_API_KEY ?? "dev-secret",
    timeoutMs: Number.isFinite(timeout) && timeout > 0 ? timeout : 5000,
  };
}
```

Modify `apps/desktop/src/lib/client.ts`:

```ts
import {
  createLocalWarmAiGateway,
  createWarmDockClient,
  type WarmDockClient,
} from "@warmdock/api";
import { warmAiConfigFromEnv } from "./warmaiConfig";

const env = import.meta.env as Record<string, string | undefined>;
const SUPABASE_URL = env.VITE_SUPABASE_URL ?? "http://127.0.0.1:54321";
const SUPABASE_KEY =
  env.VITE_SUPABASE_ANON_KEY ?? "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH";

let client: WarmDockClient | null = null;

/** Singleton cloud client. The WebView2 runtime persists the session in localStorage. */
export function getClient(): WarmDockClient {
  if (!client) {
    client = createWarmDockClient({
      supabaseUrl: SUPABASE_URL,
      supabaseKey: SUPABASE_KEY,
      auth: { persistSession: true, autoRefreshToken: true },
    });
    client.ai = createLocalWarmAiGateway(warmAiConfigFromEnv(env));
  }
  return client;
}
```

- [ ] **Step 4: Run GREEN verification**

Run:

```powershell
pnpm --filter @warmdock/desktop exec vitest run src/lib/warmaiConfig.test.ts
pnpm --filter @warmdock/desktop typecheck
```

Expected: tests pass and typecheck exits 0.

- [ ] **Step 5: Add Task 3 report**

Create `docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-03-desktop-wiring.md` with scope, RED/GREEN evidence, verification commands, changed files, and commit message.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add apps/desktop/src/lib/warmaiConfig.ts apps/desktop/src/lib/warmaiConfig.test.ts apps/desktop/src/lib/client.ts docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-03-desktop-wiring.md
git commit -m "feat: wire WarmAI into desktop client"
```

## Task 4: Use WarmAI Suggestions in `TaskDetailModal`

**Files:**
- Create: `G:/Micp/WarmDock/packages/ui-web/src/ui/task/aiSuggestion.ts`
- Create: `G:/Micp/WarmDock/packages/ui-web/src/ui/task/aiSuggestion.test.ts`
- Modify: `G:/Micp/WarmDock/packages/ui-web/src/ui/task/TaskDetailModal.tsx`
- Create report: `G:/Micp/WarmDock/docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-04-task-modal.md`

- [ ] **Step 1: Write the failing suggestion-state tests**

Create `packages/ui-web/src/ui/task/aiSuggestion.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { resolveTaskSuggestion } from "./aiSuggestion";

describe("resolveTaskSuggestion", () => {
  it("uses local fallback while AI is pending", () => {
    expect(resolveTaskSuggestion("deploy production", null)).toEqual({
      suggestedBand: "hard",
      suggestedScore: null,
      aiAvailable: false,
    });
  });

  it("uses AI score and band when available", () => {
    expect(
      resolveTaskSuggestion("Clena the desk", {
        originalText: "Clena the desk",
        suggestedCorrection: "Clean the desk",
        suggestedBand: "easy",
        suggestedScore: 2,
        reason: "Mock analysis.",
        available: true,
      })
    ).toEqual({
      suggestedBand: "easy",
      suggestedScore: 2,
      aiAvailable: true,
    });
  });

  it("keeps local fallback when AI is unavailable", () => {
    expect(
      resolveTaskSuggestion("reply to email", {
        originalText: "reply to email",
        suggestedCorrection: null,
        suggestedBand: "medium",
        suggestedScore: 3,
        reason: "WarmAI down.",
        available: false,
      })
    ).toEqual({
      suggestedBand: "easy",
      suggestedScore: null,
      aiAvailable: false,
    });
  });
});
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
pnpm --filter @warmdock/ui-web exec vitest run src/ui/task/aiSuggestion.test.ts
```

Expected: FAIL because `./aiSuggestion` does not exist.

- [ ] **Step 3: Implement the suggestion helper**

Create `packages/ui-web/src/ui/task/aiSuggestion.ts`:

```ts
import type { AiAnalysis } from "@warmdock/api";
import type { Difficulty, DifficultyBand } from "@warmdock/core";
import { suggestDifficulty } from "@warmdock/core/rules/task";

export interface TaskSuggestionState {
  suggestedBand: DifficultyBand;
  suggestedScore: Difficulty | null;
  aiAvailable: boolean;
}

export function resolveTaskSuggestion(
  title: string,
  analysis: AiAnalysis | null
): TaskSuggestionState {
  if (analysis?.available) {
    return {
      suggestedBand: analysis.suggestedBand,
      suggestedScore: analysis.suggestedScore,
      aiAvailable: true,
    };
  }

  return {
    suggestedBand: suggestDifficulty(title),
    suggestedScore: null,
    aiAvailable: false,
  };
}
```

- [ ] **Step 4: Modify `TaskDetailModal` to call the AI action**

Modify `packages/ui-web/src/ui/task/TaskDetailModal.tsx`:

```ts
import { useEffect, useState } from "react";
import { analyzeTaskProposal, discardTask, setTaskDetail, updateTaskTitle } from "@warmdock/app";
import { useUIStore } from "@warmdock/app";
import { useUnlockStore } from "@warmdock/app";
import { difficultyBandLabel, t } from "@warmdock/core/i18n";
import { canShowFocusTaskOption } from "@warmdock/core/rules/unlock";
import { DIFFICULTY_OPTIONS } from "@warmdock/core/rules/task";
import type { Difficulty, Task } from "@warmdock/core/types";
import type { AiAnalysis } from "@warmdock/api";
import { resolveTaskSuggestion } from "./aiSuggestion";
```

Inside the component state block, add:

```ts
  const [analysis, setAnalysis] = useState<AiAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
```

Replace the local suggestion block with:

```ts
  const suggestion = resolveTaskSuggestion(title, analysis);
  const suggested = suggestion.suggestedBand;
  const options = DIFFICULTY_OPTIONS[suggested];
```

Add this effect after the modal cleanup effect:

```ts
  useEffect(() => {
    const trimmed = title.trim();
    let cancelled = false;
    setAnalysis(null);

    if (!trimmed) return;

    setIsAnalyzing(true);
    void analyzeTaskProposal(trimmed)
      .then((result) => {
        if (cancelled) return;
        setAnalysis(result);
        if (result.available) setSelected(result.suggestedScore);
      })
      .finally(() => {
        if (!cancelled) setIsAnalyzing(false);
      });

    return () => {
      cancelled = true;
    };
  }, [title]);
```

Update the hint text without changing layout:

```tsx
        <p className="wd-modal__hint">
          {t("detail.suggestion", { band: difficultyBandLabel(suggested) })}
          {isAnalyzing ? " ..." : ""}
        </p>
```

- [ ] **Step 5: Run GREEN verification**

Run:

```powershell
pnpm --filter @warmdock/ui-web exec vitest run src/ui/task/aiSuggestion.test.ts
pnpm --filter @warmdock/ui-web typecheck
```

Expected: tests pass and typecheck exits 0.

- [ ] **Step 6: Add Task 4 report**

Create `docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-04-task-modal.md` with scope, RED/GREEN evidence, verification commands, changed files, and commit message.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add packages/ui-web/src/ui/task/aiSuggestion.ts packages/ui-web/src/ui/task/aiSuggestion.test.ts packages/ui-web/src/ui/task/TaskDetailModal.tsx docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-04-task-modal.md
git commit -m "feat: use WarmAI suggestions in task modal"
```

## Task 5: Full Verification and Manual Mock E2E

**Files:**
- Create report: `G:/Micp/WarmDock/docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-05-verification.md`

- [ ] **Step 1: Run focused package tests**

Run from `G:/Micp/WarmDock`:

```powershell
pnpm --filter @warmdock/api test
pnpm --filter @warmdock/app test
pnpm --filter @warmdock/ui-web test
pnpm --filter @warmdock/desktop test
```

Expected: all non-gated tests pass.

- [ ] **Step 2: Run typechecks**

Run:

```powershell
pnpm --filter @warmdock/api typecheck
pnpm --filter @warmdock/app typecheck
pnpm --filter @warmdock/ui-web typecheck
pnpm --filter @warmdock/desktop typecheck
```

Expected: all commands exit 0.

- [ ] **Step 3: Run repository-level verification**

Run:

```powershell
pnpm test
pnpm typecheck
```

Expected: all workspace tests and typechecks pass.

- [ ] **Step 4: Run manual mock E2E**

Confirm WarmAI is running in another terminal:

```powershell
cd G:\Micp\WarmAI
$env:WARMAI_API_KEY="dev-secret"
$env:WARMAI_ADAPTER_KIND="mock"
.\.venv\Scripts\python.exe -m uvicorn warmai.main:app --host 127.0.0.1 --port 8000
```

Start WarmDock Desktop:

```powershell
cd G:\Micp\WarmDock
pnpm --filter @warmdock/desktop dev
```

Manual checks:

- Sign in as usual.
- Create a draft task.
- Open the task detail modal.
- Confirm the suggestion remains usable while analysis is pending.
- Confirm a WarmAI-backed mock suggestion appears when WarmAI responds.
- Stop WarmAI.
- Edit or create another task.
- Confirm the modal still works with local fallback.

- [ ] **Step 5: Add Task 5 report**

Create `docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-05-verification.md` with verification output, manual E2E notes, changed files, commits, and any residual risks.

- [ ] **Step 6: Commit Task 5 report**

Run:

```powershell
git add docs/task-reports/YYYY-MM-DD-warmdock-warmai-task-05-verification.md
git commit -m "docs: verify WarmDock WarmAI mock integration"
```

## Final Verification Checklist

- [ ] WarmAI mock server responds at `http://127.0.0.1:8000/v1/task-analysis`.
- [ ] WarmDock Desktop calls WarmAI through `AiGateway`.
- [ ] WarmDock maps WarmAI score 1-5 to easy/medium/hard.
- [ ] WarmDock task setup still works when WarmAI is down.
- [ ] No Qwen3-4B, llama.cpp, QLoRA, or training work is introduced.
- [ ] `pnpm test` passes in WarmDock.
- [ ] `pnpm typecheck` passes in WarmDock.
- [ ] Each task has a report under `G:/Micp/WarmDock/docs/task-reports/`.
