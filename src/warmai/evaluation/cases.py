from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScoreEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_type: Literal["score"] = "score"
    case_id: str
    text: str = Field(min_length=1, max_length=200)
    expected_language: str
    expected_score: int = Field(ge=1, le=5)
    correction_expected: bool


class HttpEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_type: Literal["http"] = "http"
    case_id: str
    text: str = Field(min_length=1, max_length=200)
    expected_http_status: int = Field(ge=100, le=599)
    expected_error_code: str | None


EvaluationCase = ScoreEvaluationCase | HttpEvaluationCase


def parse_case(payload: object) -> EvaluationCase:
    if not isinstance(payload, dict):
        raise TypeError("evaluation case must be a JSON object")
    if "expected_http_status" in payload:
        return HttpEvaluationCase.model_validate(payload)
    return ScoreEvaluationCase.model_validate(payload)
