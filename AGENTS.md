# Project Context

<!-- This file is maintained by humans and Archivist. Archivist must never write here before user confirmation. -->

## Architecture Decisions


## Coding Style


## Workflow


- After every implementation-plan task, create a Markdown completion report under `docs/task-reports/` containing scope, TDD evidence, verification results, changed files, and commit information.

## Tooling


## Project Rules


---

## Archivist 觸發規則

當使用者在對話中輸入 `Archivist sync`（或 `archivist sync`）時，這不是一般訊息，而是要求你執行「記憶歸檔」流程。若介面允許純文字 `@Archivist`，也可視為同一觸發；但在 Codex App 中優先使用 `Archivist sync`，避免 `@` 被解析成檔案或資料夾 mention。收到此觸發時，嚴格依照下列步驟進行：

1. 讀取 `.archivist/prompt.md`，那是你執行整理時要扮演的角色與規格。
2. 讀取 `.archivist/state.json`，了解上次同步的時間與狀態。
3. 把「自上次同步以來、目前你能看到的對話上下文中」值得長期保存的專案知識，整理寫入 `.archivist/inbox.md`（覆寫，不要累加舊內容）。
4. 依 `prompt.md` 的規格，比對 inbox、現有 AGENTS.md、state.json，產出條列式的「建議新增 / 修改 / 刪除 / 衝突」，寫入 `.archivist/proposed.patch.md` 作為暫存紀錄。
5. 把同一份 proposed.patch.md 內容貼到 chat 中，等待使用者在 chat 明確確認要接受哪幾項。**在使用者明確回覆前，絕不修改本 AGENTS.md。**
6. 使用者在 chat 確認後，只把被接受的項目套用到本檔對應章節，然後更新 state.json。

關鍵約束：寫入 AGENTS.md 永遠是流程的最後一步，且永遠需要使用者確認。寧可少記，不可亂記。
