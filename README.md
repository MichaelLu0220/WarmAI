# WarmAI

WarmAI is the local model service for WarmDock task correction and 1-5 difficulty scoring.

## MVP Scope

The MVP provides one synchronous `POST /v1/task-analysis` endpoint, a CLI, masked SQLite
logging, bounded fallback, and mock or llama.cpp inference. It does not provide streaming,
batch inference, QLoRA, teacher labeling, a WarmDock Agent, or production remote deployment.

## WSL2 Setup

```bash
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install uv
uv sync --extra dev
```

Set a local key in `.env`:

```dotenv
WARMAI_API_KEY=dev-secret
WARMAI_ADAPTER_KIND=mock
```

## Run With The Mock Adapter

```bash
uvicorn warmai.main:app --host 127.0.0.1 --port 8000
warmai "整理房間" --api-key dev-secret
```

## Run Qwen3-8B With local llama.cpp

The tested Windows setup keeps large local files out of Git:

- Model: `models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf`
- llama.cpp: `tools/llama.cpp/b9735-cuda-12.4/`

Start llama.cpp first:

```powershell
cd G:\Micp\WarmAI
.\tools\llama.cpp\b9735-cuda-12.4\llama-server.exe `
  --model .\models\qwen3-8b\Qwen3-8B-Q4_K_M.gguf `
  --alias qwen3-8b-q4 `
  --host 127.0.0.1 `
  --port 8080 `
  --ctx-size 4096 `
  --n-gpu-layers all `
  --jinja
```

Update `.env`:

```dotenv
WARMAI_ADAPTER_KIND=llama_cpp
WARMAI_LLAMA_CPP_BASE_URL=http://127.0.0.1:8080
WARMAI_LLAMA_CPP_MODEL=qwen3-8b-q4
```

Then start WarmAI:

```powershell
cd G:\Micp\WarmAI
.\.venv\Scripts\python.exe -m uvicorn warmai.main:app --host 127.0.0.1 --port 8000
```

## Verify

```bash
ruff format --check .
ruff check .
mypy src/warmai
python -m pytest -v
```

Opt into the real model smoke test:

```bash
WARMAI_RUN_REAL_MODEL_SMOKE=1 \
python -m pytest tests/smoke/test_real_adapter.py -v
```

Run evaluation:

```bash
warmai-evaluate \
  --dataset evaluation/core.jsonl \
  --base-url http://127.0.0.1:8000 \
  --api-key dev-secret
```

Reports are written to `reports/latest.json`, `reports/history/`, and `reports/summary.md`.

## Privacy

WarmAI masks detected PII before SQLite persistence and excludes those rows from training
candidates. The database can still contain sensitive operational metadata; keep `data/warmai.db`
private and do not publish it.
