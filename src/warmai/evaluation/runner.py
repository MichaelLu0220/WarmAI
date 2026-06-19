import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from warmai.evaluation.cases import EvaluationCase
from warmai.evaluation.metrics import EvaluationSample, EvaluationSummary, summarize
from warmai.evaluation.reporting import write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    return parser.parse_args()


def load_cases(path: Path) -> list[EvaluationCase]:
    return [
        EvaluationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run_cases(
    cases: list[EvaluationCase],
    base_url: str,
    api_key: str,
) -> list[EvaluationSample]:
    samples: list[EvaluationSample] = []
    with httpx.Client(timeout=5.0) as client:
        for case in cases:
            request_id = str(uuid4())
            response = client.post(
                f"{base_url.rstrip('/')}/v1/task-analysis",
                headers={
                    "X-API-Key": api_key,
                    "Idempotency-Key": request_id,
                },
                json={"text": case.text, "client_request_id": request_id},
            )
            try:
                body: dict[str, Any] = response.json()
            except ValueError:
                body = {}
            valid = response.status_code == 200 and body.get("status") in {
                "ok",
                "degraded",
            }
            result = body.get("result", {})
            trace = body.get("trace", {})
            samples.append(
                EvaluationSample(
                    expected_score=case.expected_score,
                    actual_score=int(result.get("score", 0)),
                    valid_json=valid,
                    latency_ms=int(body.get("latency_ms", 5000)),
                    language_preserved=result.get("language") == case.expected_language,
                    fallback_used=trace.get("fallback_stage") != "none",
                    unnecessary_correction=(
                        not case.correction_expected and result.get("suggested_text") is not None
                    ),
                )
            )
    return samples


def passes_mvp_gates(summary: EvaluationSummary) -> bool:
    return (
        summary.score_within_one_rate >= 0.80
        and summary.valid_json_rate >= 0.99
        and summary.language_preservation_rate == 1.0
        and summary.p95_latency_ms < 5000
    )


def main() -> None:
    args = parse_args()
    cases = load_cases(args.dataset)
    samples = run_cases(cases, args.base_url, args.api_key)
    summary = summarize(samples)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    write_report(Path("reports"), summary, run_id)
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
    raise SystemExit(0 if passes_mvp_gates(summary) else 1)


if __name__ == "__main__":
    main()
