import json
from dataclasses import asdict
from pathlib import Path

from warmai.evaluation.metrics import EvaluationSample, EvaluationSummary


def failure_issues(sample: EvaluationSample) -> list[str]:
    issues: list[str] = []
    if sample.case_type == "http":
        if sample.status_code != sample.expected_http_status:
            issues.append("expected_status_mismatch")
        if sample.expected_http_status == 200 and sample.actual_error_code is not None:
            issues.append("unexpected_error_response")
            return issues
        if sample.actual_error_code != sample.expected_error_code:
            issues.append("expected_error_code_mismatch")
        return issues
    if not sample.valid_json:
        issues.append("invalid_response")
    if abs(sample.actual_score - sample.expected_score) > 1:
        issues.append("score_delta_outside_one")
    if not sample.language_preserved:
        issues.append("language_changed")
    if sample.unnecessary_correction:
        issues.append("unnecessary_correction")
    return issues


def failure_payload(sample: EvaluationSample) -> dict[str, object]:
    return {
        "case_id": sample.case_id,
        "text": sample.text,
        "issues": failure_issues(sample),
        "expected_score": sample.expected_score,
        "actual_score": sample.actual_score,
        "expected_language": sample.expected_language,
        "actual_language": sample.actual_language,
        "valid_json": sample.valid_json,
        "status_code": sample.status_code,
        "response_status": sample.response_status,
        "latency_ms": sample.latency_ms,
        "fallback_stage": sample.fallback_stage,
        "correction_expected": sample.correction_expected,
        "suggested_text_present": sample.suggested_text_present,
        "case_type": sample.case_type,
        "expected_http_status": sample.expected_http_status,
        "expected_error_code": sample.expected_error_code,
        "actual_error_code": sample.actual_error_code,
        "http_contract_passed": sample.http_contract_passed,
    }


def _write_failure_reports(
    directory: Path,
    history: Path,
    samples: list[EvaluationSample],
    run_id: str,
) -> None:
    failures = [sample for sample in samples if failure_issues(sample)]
    jsonl = "\n".join(
        json.dumps(failure_payload(sample), ensure_ascii=False, sort_keys=True)
        for sample in failures
    )
    if jsonl:
        jsonl += "\n"
    (directory / "latest_failures.jsonl").write_text(jsonl, encoding="utf-8")
    (history / f"{run_id}-failures.jsonl").write_text(jsonl, encoding="utf-8")

    if not failures:
        markdown = "# WarmAI Evaluation Failures\n\nNo failing cases.\n"
    else:
        rows = [
            "# WarmAI Evaluation Failures",
            "",
            "| Case | Issues | Expected | Actual | Language | Latency |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for sample in failures:
            rows.append(
                "| "
                f"{sample.case_id} | "
                f"{', '.join(failure_issues(sample))} | "
                f"{sample.expected_score} | "
                f"{sample.actual_score} | "
                f"{sample.expected_language} -> {sample.actual_language} | "
                f"{sample.latency_ms} ms |"
            )
        markdown = "\n".join(rows) + "\n"
    (directory / "failures.md").write_text(markdown, encoding="utf-8")


def write_report(
    directory: Path,
    summary: EvaluationSummary,
    run_id: str,
    samples: list[EvaluationSample] | None = None,
) -> None:
    history = directory / "history"
    history.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(summary), indent=2, sort_keys=True)
    (directory / "latest.json").write_text(payload + "\n", encoding="utf-8")
    (history / f"{run_id}.json").write_text(payload + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(
        "# WarmAI Evaluation\n\n"
        f"- Cases: {summary.total}\n"
        f"- Score within 1: {summary.score_within_one_rate:.1%}\n"
        f"- Valid JSON: {summary.valid_json_rate:.1%}\n"
        f"- Language preserved: {summary.language_preservation_rate:.1%}\n"
        f"- Fallback rate: {summary.fallback_rate:.1%}\n"
        f"- Unnecessary corrections: {summary.unnecessary_correction_rate:.1%}\n"
        f"- HTTP contract pass: {summary.http_contract_pass_rate:.1%}\n"
        f"- p95 latency: {summary.p95_latency_ms} ms\n",
        encoding="utf-8",
    )
    if samples is not None:
        _write_failure_reports(directory, history, samples, run_id)
