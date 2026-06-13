from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr

from warmai.contracts.common import ResponseStatus, StrictModel
from warmai.contracts.task_analysis import UuidText


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNAUTHORIZED = "UNAUTHORIZED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    IDEMPOTENCY_IN_PROGRESS = "IDEMPOTENCY_IN_PROGRESS"
    IDEMPOTENCY_RESULT_UNAVAILABLE = "IDEMPOTENCY_RESULT_UNAVAILABLE"
    UNANALYZABLE_INPUT = "UNANALYZABLE_INPUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorDetail(StrictModel):
    code: ErrorCode
    message: StrictStr
    retryable: StrictBool


class ErrorResponse(StrictModel):
    request_id: UuidText
    schema_version: StrictStr
    status: Literal[ResponseStatus.ERROR]
    error: ErrorDetail
    latency_ms: Annotated[StrictInt, Field(ge=0)]
