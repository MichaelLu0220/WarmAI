import pytest
from pydantic import ValidationError

from warmai.contracts.task_analysis import ModelOutput, TaskAnalysisRequest


def test_model_output_accepts_contract_bounds() -> None:
    output = ModelOutput(
        suggested_text=None,
        score=3,
        correction_confidence=0.9,
        score_confidence=0.6,
        warnings=["資訊不足"],
        reason="通常需要多個步驟。",
        is_task=True,
        needs_review=False,
    )
    assert output.score == 3


@pytest.mark.parametrize("score", [0, 6, 87])
def test_model_output_rejects_out_of_range_scores(score: int) -> None:
    with pytest.raises(ValidationError):
        ModelOutput(
            suggested_text=None,
            score=score,
            correction_confidence=0.5,
            score_confidence=0.5,
            warnings=[],
            reason="Valid reason.",
            is_task=True,
            needs_review=False,
        )


def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TaskAnalysisRequest(
            text="Clean the desk",
            client_request_id="123e4567-e89b-12d3-a456-426614174000",
            extra_field=True,
        )
