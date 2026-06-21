import pytest

from warmai.evaluation.metrics import EvaluationSample, summarize


def test_score_within_one_metric() -> None:
    summary = summarize(
        [
            EvaluationSample(
                expected_score=3,
                actual_score=4,
                valid_json=True,
                latency_ms=10,
            ),
            EvaluationSample(
                expected_score=1,
                actual_score=5,
                valid_json=True,
                latency_ms=20,
                unnecessary_correction=True,
            ),
        ]
    )

    assert summary.total == 2
    assert summary.score_within_one_rate == 0.5
    assert summary.valid_json_rate == 1.0
    assert summary.language_preservation_rate == 1.0
    assert summary.fallback_rate == 0.0
    assert summary.unnecessary_correction_rate == 0.5
    assert summary.p95_latency_ms == 20


def test_summary_rates_and_p95_are_deterministic() -> None:
    summary = summarize(
        [
            EvaluationSample(
                expected_score=1,
                actual_score=1,
                valid_json=True,
                latency_ms=50,
                language_preserved=True,
                fallback_used=False,
            ),
            EvaluationSample(
                expected_score=5,
                actual_score=3,
                valid_json=False,
                latency_ms=10,
                language_preserved=False,
                fallback_used=True,
            ),
            EvaluationSample(
                expected_score=3,
                actual_score=2,
                valid_json=True,
                latency_ms=30,
                language_preserved=True,
                fallback_used=True,
            ),
        ]
    )

    assert summary.score_within_one_rate == pytest.approx(2 / 3)
    assert summary.valid_json_rate == pytest.approx(2 / 3)
    assert summary.language_preservation_rate == pytest.approx(2 / 3)
    assert summary.fallback_rate == pytest.approx(2 / 3)
    assert summary.http_contract_pass_rate == 1.0
    assert summary.p95_latency_ms == 50


def test_http_contract_pass_rate_counts_only_http_cases() -> None:
    summary = summarize(
        [
            EvaluationSample(
                case_type="score",
                expected_score=2,
                actual_score=2,
                valid_json=True,
                latency_ms=10,
            ),
            EvaluationSample(
                case_type="http",
                expected_score=0,
                actual_score=0,
                valid_json=True,
                latency_ms=20,
                http_contract_passed=True,
            ),
            EvaluationSample(
                case_type="http",
                expected_score=0,
                actual_score=0,
                valid_json=True,
                latency_ms=30,
                http_contract_passed=False,
            ),
        ]
    )

    assert summary.http_contract_pass_rate == pytest.approx(0.5)


def test_empty_evaluation_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        summarize([])
