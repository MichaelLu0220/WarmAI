import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from warmai.evaluation.cases import (
    EvaluationCase,
    HttpEvaluationCase,
    ScoreEvaluationCase,
    parse_case,
)
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
        parse_case(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _error_code(body: dict[str, Any]) -> str | None:
    error = body.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    if not isinstance(code, str):
        return None
    return code


def _score_sample(
    case: ScoreEvaluationCase,
    response: httpx.Response,
    body: dict[str, Any],
) -> EvaluationSample:
    valid = response.status_code == 200 and body.get("status") in {
        "ok",
        "degraded",
    }
    result = body.get("result", {})
    trace = body.get("trace", {})
    suggested_text_present = result.get("suggested_text") is not None
    fallback_stage = trace.get("fallback_stage")
    return EvaluationSample(
        case_type=case.case_type,
        case_id=case.case_id,
        text=case.text,
        expected_score=case.expected_score,
        actual_score=int(result.get("score", 0)),
        valid_json=valid,
        latency_ms=int(body.get("latency_ms", 5000)),
        expected_language=case.expected_language,
        actual_language=result.get("language"),
        language_preserved=result.get("language") == case.expected_language,
        fallback_used=fallback_stage != "none",
        unnecessary_correction=not case.correction_expected and suggested_text_present,
        correction_expected=case.correction_expected,
        suggested_text_present=suggested_text_present,
        status_code=response.status_code,
        response_status=body.get("status"),
        fallback_stage=fallback_stage,
    )


def _http_sample(
    case: HttpEvaluationCase,
    response: httpx.Response,
    body: dict[str, Any],
    valid_json: bool,
) -> EvaluationSample:
    actual_error_code = _error_code(body)
    return EvaluationSample(
        case_type=case.case_type,
        case_id=case.case_id,
        text=case.text,
        expected_score=0,
        actual_score=0,
        valid_json=valid_json,
        latency_ms=int(body.get("latency_ms", 5000)),
        status_code=response.status_code,
        response_status=body.get("status"),
        expected_http_status=case.expected_http_status,
        expected_error_code=case.expected_error_code,
        actual_error_code=actual_error_code,
        http_contract_passed=(
            response.status_code == case.expected_http_status
            and actual_error_code == case.expected_error_code
        ),
    )


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
                valid_json = True
            except ValueError:
                body = {}
                valid_json = False
            if isinstance(case, ScoreEvaluationCase):
                samples.append(_score_sample(case, response, body))
            else:
                samples.append(_http_sample(case, response, body, valid_json))
    return samples


def passes_mvp_gates(summary: EvaluationSummary) -> bool:
    return (
        summary.score_within_one_rate >= 0.80
        and summary.valid_json_rate >= 0.99
        and summary.language_preservation_rate == 1.0
        and summary.http_contract_pass_rate == 1.0
        and summary.p95_latency_ms < 5000
    )


def main() -> None:
    args = parse_args()
    cases = load_cases(args.dataset)
    samples = run_cases(cases, args.base_url, args.api_key)
    summary = summarize(samples)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    write_report(Path("reports"), summary, run_id, samples=samples)
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
    raise SystemExit(0 if passes_mvp_gates(summary) else 1)


if __name__ == "__main__":
    main()
