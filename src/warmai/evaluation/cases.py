from pydantic import BaseModel, ConfigDict, Field


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    text: str = Field(min_length=1, max_length=200)
    expected_language: str
    expected_score: int = Field(ge=1, le=5)
    correction_expected: bool
