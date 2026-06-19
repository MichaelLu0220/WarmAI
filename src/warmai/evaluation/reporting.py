import json
from dataclasses import asdict
from pathlib import Path

from warmai.evaluation.metrics import EvaluationSummary


def write_report(directory: Path, summary: EvaluationSummary, run_id: str) -> None:
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
        f"- p95 latency: {summary.p95_latency_ms} ms\n",
        encoding="utf-8",
    )
