from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class EvaluationSample:
    expected_score: int
    actual_score: int
    valid_json: bool
    latency_ms: int
    case_type: str = "score"
    language_preserved: bool = True
    fallback_used: bool = False
    unnecessary_correction: bool = False
    case_id: str = ""
    text: str = ""
    expected_language: str = ""
    actual_language: str | None = None
    correction_expected: bool = False
    suggested_text_present: bool = False
    status_code: int = 0
    response_status: str | None = None
    fallback_stage: str | None = None
    expected_http_status: int | None = None
    expected_error_code: str | None = None
    actual_error_code: str | None = None
    http_contract_passed: bool = True


@dataclass(frozen=True)
class EvaluationSummary:
    total: int
    score_within_one_rate: float
    valid_json_rate: float
    language_preservation_rate: float
    fallback_rate: float
    unnecessary_correction_rate: float
    http_contract_pass_rate: float
    p95_latency_ms: int


def _rate(passed: int, total: int, default: float) -> float:
    if total == 0:
        return default
    return passed / total


def summarize(samples: list[EvaluationSample]) -> EvaluationSummary:
    if not samples:
        raise ValueError("evaluation requires at least one sample")

    ordered = sorted(sample.latency_ms for sample in samples)
    p95_index = max(0, ceil(len(ordered) * 0.95) - 1)
    total = len(samples)
    score_samples = [sample for sample in samples if sample.case_type == "score"]
    http_samples = [sample for sample in samples if sample.case_type == "http"]
    return EvaluationSummary(
        total=total,
        score_within_one_rate=_rate(
            sum(abs(item.actual_score - item.expected_score) <= 1 for item in score_samples),
            len(score_samples),
            1.0,
        ),
        valid_json_rate=sum(item.valid_json for item in samples) / total,
        language_preservation_rate=_rate(
            sum(item.language_preserved for item in score_samples),
            len(score_samples),
            1.0,
        ),
        fallback_rate=_rate(
            sum(item.fallback_used for item in score_samples),
            len(score_samples),
            0.0,
        ),
        unnecessary_correction_rate=_rate(
            sum(item.unnecessary_correction for item in score_samples),
            len(score_samples),
            0.0,
        ),
        http_contract_pass_rate=_rate(
            sum(item.http_contract_passed for item in http_samples),
            len(http_samples),
            1.0,
        ),
        p95_latency_ms=ordered[p95_index],
    )
