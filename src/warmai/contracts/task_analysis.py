from typing import Annotated

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr

from warmai.contracts.common import (
    FallbackStage,
    Language,
    PrimaryLanguage,
    ResponseStatus,
    StrictModel,
)

UuidText = Annotated[
    StrictStr,
    Field(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
    ),
]
ShortText = Annotated[StrictStr, Field(min_length=1, max_length=200)]
Confidence = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
WarningText = Annotated[StrictStr, Field(min_length=1, max_length=100)]


class TaskAnalysisRequest(StrictModel):
    text: ShortText
    client_request_id: UuidText


class ModelOutput(StrictModel):
    suggested_text: Annotated[StrictStr, Field(min_length=1, max_length=200)] | None
    score: Annotated[StrictInt, Field(ge=1, le=5)]
    correction_confidence: Confidence
    score_confidence: Confidence
    warnings: Annotated[list[WarningText], Field(max_length=5)]
    reason: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    needs_review: StrictBool


class TaskAnalysisResult(ModelOutput):
    language: Language
    primary_language: PrimaryLanguage
    original_text: ShortText


class Trace(StrictModel):
    model_version: StrictStr
    prompt_version: StrictStr
    fallback_stage: FallbackStage


class TaskAnalysisResponse(StrictModel):
    request_id: UuidText
    schema_version: StrictStr
    status: ResponseStatus
    result: TaskAnalysisResult
    trace: Trace
    latency_ms: Annotated[StrictInt, Field(ge=0)]
