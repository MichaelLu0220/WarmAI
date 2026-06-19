from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class EvaluationSample:
    expected_score: int
    actual_score: int
    valid_json: bool
    latency_ms: int
    language_preserved: bool = True
    fallback_used: bool = False
    unnecessary_correction: bool = False


@dataclass(frozen=True)
class EvaluationSummary:
    total: int
    score_within_one_rate: float
    valid_json_rate: float
    language_preservation_rate: float
    fallback_rate: float
    unnecessary_correction_rate: float
    p95_latency_ms: int


def summarize(samples: list[EvaluationSample]) -> EvaluationSummary:
    if not samples:
        raise ValueError("evaluation requires at least one sample")

    ordered = sorted(sample.latency_ms for sample in samples)
    p95_index = max(0, ceil(len(ordered) * 0.95) - 1)
    total = len(samples)
    return EvaluationSummary(
        total=total,
        score_within_one_rate=sum(
            abs(item.actual_score - item.expected_score) <= 1 for item in samples
        )
        / total,
        valid_json_rate=sum(item.valid_json for item in samples) / total,
        language_preservation_rate=sum(item.language_preserved for item in samples) / total,
        fallback_rate=sum(item.fallback_used for item in samples) / total,
        unnecessary_correction_rate=sum(item.unnecessary_correction for item in samples) / total,
        p95_latency_ms=ordered[p95_index],
    )
