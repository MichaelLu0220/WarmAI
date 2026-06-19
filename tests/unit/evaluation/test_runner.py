from pathlib import Path

import httpx
import pytest

from warmai.evaluation.metrics import EvaluationSummary
from warmai.evaluation.runner import (
    load_cases,
    passes_mvp_gates,
    run_cases,
)


def test_load_cases_reads_jsonl(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        '{"case_id":"case-1","text":"Clean the desk",'
        '"expected_language":"en","expected_score":2,'
        '"correction_expected":false}\n\n',
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert len(cases) == 1
    assert cases[0].case_id == "case-1"
    assert cases[0].expected_score == 2


def test_run_cases_collects_http_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = [
        {
            "case_id": "case-1",
            "text": "Clean the desk",
            "expected_language": "en",
            "expected_score": 2,
            "correction_expected": False,
        }
    ]
    cases = [
        __import__("warmai.evaluation.cases", fromlist=["EvaluationCase"]).EvaluationCase(**item)
        for item in dataset
    ]
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "json": __import__("json").loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "score": 3,
                    "language": "en",
                    "suggested_text": None,
                },
                "trace": {"fallback_stage": "none"},
                "latency_ms": 123,
            },
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        "warmai.evaluation.runner.httpx.Client",
        lambda timeout: original_client(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
        ),
    )
    monkeypatch.setattr("warmai.evaluation.runner.uuid4", lambda: "request-id")

    samples = run_cases(cases, "http://api/", "secret")

    assert len(samples) == 1
    assert samples[0].expected_score == 2
    assert samples[0].actual_score == 3
    assert samples[0].valid_json is True
    assert samples[0].latency_ms == 123
    assert samples[0].language_preserved is True
    assert samples[0].fallback_used is False
    assert requests[0]["url"] == "http://api/v1/task-analysis"
    assert requests[0]["json"] == {
        "text": "Clean the desk",
        "client_request_id": "request-id",
    }


def test_mvp_gates() -> None:
    passing = EvaluationSummary(
        total=1,
        score_within_one_rate=0.8,
        valid_json_rate=1.0,
        language_preservation_rate=1.0,
        fallback_rate=0.0,
        unnecessary_correction_rate=0.0,
        p95_latency_ms=4999,
    )
    failing = EvaluationSummary(
        total=1,
        score_within_one_rate=0.79,
        valid_json_rate=1.0,
        language_preservation_rate=1.0,
        fallback_rate=0.0,
        unnecessary_correction_rate=0.0,
        p95_latency_ms=100,
    )

    assert passes_mvp_gates(passing) is True
    assert passes_mvp_gates(failing) is False
