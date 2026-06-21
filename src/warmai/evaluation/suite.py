import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from warmai.evaluation.metrics import EvaluationSample, EvaluationSummary, summarize
from warmai.evaluation.reporting import failure_issues, failure_payload
from warmai.evaluation.runner import load_cases, passes_mvp_gates, run_cases


@dataclass(frozen=True)
class EvaluationDataset:
    name: str
    path: Path


@dataclass(frozen=True)
class SuiteDatasetResult:
    name: str
    dataset: Path
    summary: EvaluationSummary
    passed: bool
    samples: list[EvaluationSample]


DEFAULT_DATASETS = (
    EvaluationDataset("core", Path("evaluation/core.jsonl")),
    EvaluationDataset("hard_cases", Path("evaluation/hard_cases.jsonl")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    return parser.parse_args()


def run_suite(
    base_url: str,
    api_key: str,
    datasets: tuple[EvaluationDataset, ...] | list[EvaluationDataset] = DEFAULT_DATASETS,
) -> list[SuiteDatasetResult]:
    results: list[SuiteDatasetResult] = []
    for dataset in datasets:
        cases = load_cases(dataset.path)
        samples = run_cases(cases, base_url, api_key)
        summary = summarize(samples)
        results.append(
            SuiteDatasetResult(
                name=dataset.name,
                dataset=dataset.path,
                summary=summary,
                passed=passes_mvp_gates(summary),
                samples=samples,
            )
        )
    return results


def suite_passed(results: list[SuiteDatasetResult]) -> bool:
    return all(result.passed for result in results)


def _result_payload(result: SuiteDatasetResult) -> dict[str, object]:
    failures = [failure_payload(sample) for sample in result.samples if failure_issues(sample)]
    return {
        "name": result.name,
        "dataset": str(result.dataset),
        "passed": result.passed,
        "summary": asdict(result.summary),
        "failures": failures,
    }


def _summary_markdown(results: list[SuiteDatasetResult]) -> str:
    rows = [
        "# WarmAI Evaluation Suite",
        "",
        f"- Overall: {'PASS' if suite_passed(results) else 'FAIL'}",
        "",
        "| Dataset | Result | Cases | Score within 1 | Valid JSON | Language | "
        "HTTP contract | p95 latency |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        summary = result.summary
        rows.append(
            "| "
            f"{result.name} | "
            f"{'PASS' if result.passed else 'FAIL'} | "
            f"{summary.total} | "
            f"{summary.score_within_one_rate:.1%} | "
            f"{summary.valid_json_rate:.1%} | "
            f"{summary.language_preservation_rate:.1%} | "
            f"{summary.http_contract_pass_rate:.1%} | "
            f"{summary.p95_latency_ms} ms |"
        )
    return "\n".join(rows) + "\n"


def _failures_markdown(results: list[SuiteDatasetResult]) -> str:
    rows = ["# WarmAI Evaluation Suite Failures", ""]
    failures: list[tuple[str, EvaluationSample]] = []
    for result in results:
        failures.extend(
            (result.name, sample) for sample in result.samples if failure_issues(sample)
        )
    if not failures:
        return "\n".join([*rows, "No failing cases."]) + "\n"

    rows.extend(
        [
            "| Dataset | Case | Issues | Expected | Actual | Language | Latency |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for dataset_name, sample in failures:
        rows.append(
            "| "
            f"{dataset_name} | "
            f"{sample.case_id} | "
            f"{', '.join(failure_issues(sample))} | "
            f"{sample.expected_score} | "
            f"{sample.actual_score} | "
            f"{sample.expected_language} -> {sample.actual_language} | "
            f"{sample.latency_ms} ms |"
        )
    return "\n".join(rows) + "\n"


def write_suite_report(directory: Path, results: list[SuiteDatasetResult], run_id: str) -> None:
    history = directory / "history"
    history.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "overall_passed": suite_passed(results),
        "datasets": [_result_payload(result) for result in results],
    }
    json_payload = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    (directory / "latest.json").write_text(json_payload + "\n", encoding="utf-8")
    (history / f"{run_id}.json").write_text(json_payload + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(_summary_markdown(results), encoding="utf-8")
    (directory / "failures.md").write_text(_failures_markdown(results), encoding="utf-8")


def main() -> None:
    args = parse_args()
    results = run_suite(args.base_url, args.api_key)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    write_suite_report(Path("reports") / "suite", results, run_id)
    payload = {
        "overall_passed": suite_passed(results),
        "datasets": [_result_payload(result) for result in results],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if suite_passed(results) else 1)


if __name__ == "__main__":
    main()
