import logging
import time
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request

from warmai.api.dependencies import require_api_key
from warmai.api.error_handlers import ApiProblem
from warmai.config.model_config import PROMPT_VERSION, SCHEMA_VERSION
from warmai.contracts.errors import ErrorCode
from warmai.contracts.task_analysis import (
    TaskAnalysisRequest,
    TaskAnalysisResponse,
    TaskAnalysisResult,
    Trace,
)
from warmai.inference.deadline import Deadline
from warmai.inference.service import InferenceResult
from warmai.persistence.events import InferenceEvent
from warmai.persistence.idempotency import (
    IdempotencyConflict,
    IdempotencyInProgress,
    IdempotencyResultUnavailable,
)
from warmai.privacy.masking import mask_text
from warmai.privacy.pii import detect_pii
from warmai.text.language import LanguageClassificationError, classify_language

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])
logger = logging.getLogger(__name__)


def _idempotency_problem(error: Exception) -> ApiProblem:
    if isinstance(error, IdempotencyConflict):
        return ApiProblem(
            409,
            ErrorCode.IDEMPOTENCY_CONFLICT,
            "Idempotency key was already used with different input.",
        )
    if isinstance(error, IdempotencyInProgress):
        return ApiProblem(
            409,
            ErrorCode.IDEMPOTENCY_IN_PROGRESS,
            "The original request is still in progress.",
            retryable=True,
        )
    return ApiProblem(
        409,
        ErrorCode.IDEMPOTENCY_RESULT_UNAVAILABLE,
        "The unmasked PII response is no longer available.",
    )


async def _persist_masked_event(
    request: Request,
    body: TaskAnalysisRequest,
    response: TaskAnalysisResponse,
    inference: InferenceResult,
    input_hash: str,
) -> bool:
    input_spans = detect_pii(body.text)
    raw_spans = detect_pii(inference.raw_model_output)
    response_json = response.model_dump_json()
    response_spans = detect_pii(response_json)
    pii_detected = bool(input_spans or raw_spans or response_spans)
    event = InferenceEvent(
        request_id=response.request_id,
        client_request_id=body.client_request_id,
        raw_text_masked=mask_text(body.text, input_spans),
        raw_model_output_masked=mask_text(inference.raw_model_output, raw_spans),
        response_json_masked=mask_text(response_json, response_spans),
        input_hash=input_hash,
        pii_detected=pii_detected,
        training_eligible=not pii_detected,
        model_version=response.trace.model_version,
        prompt_version=response.trace.prompt_version,
        schema_version=response.schema_version,
        latency_ms=response.latency_ms,
        validation_result=inference.validation_result,
        fallback_stage=response.trace.fallback_stage.value,
        recovered_fields=inference.recovered_fields,
        defaulted_fields=inference.defaulted_fields,
    )
    try:
        await request.app.state.events.insert(event)
    except Exception:
        logger.exception(
            "masked inference event write failed",
            extra={"request_id": response.request_id},
        )
    return pii_detected


@router.post("/task-analysis", response_model=TaskAnalysisResponse)
async def analyze_task(
    body: TaskAnalysisRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> TaskAnalysisResponse:
    request.state.started_at = time.monotonic()
    request.state.request_id = uuid4()
    input_hash = sha256(body.text.encode("utf-8")).hexdigest()

    try:
        replay = await request.app.state.idempotency.lookup(idempotency_key, input_hash)
    except (
        IdempotencyConflict,
        IdempotencyInProgress,
        IdempotencyResultUnavailable,
    ) as error:
        raise _idempotency_problem(error) from error
    if replay is not None:
        return TaskAnalysisResponse.model_validate_json(replay)

    try:
        language = classify_language(body.text)
    except LanguageClassificationError as error:
        raise ApiProblem(
            400,
            ErrorCode.UNANALYZABLE_INPUT,
            "Input must contain analyzable Traditional Chinese or English.",
        ) from error

    try:
        await request.app.state.idempotency.reserve(
            idempotency_key,
            input_hash,
            str(request.state.request_id),
        )
    except (IdempotencyConflict, IdempotencyInProgress) as error:
        raise _idempotency_problem(error) from error

    inference = await request.app.state.inference.analyze(
        text=body.text,
        primary_language=language.primary_language,
        deadline=Deadline.after(request.app.state.settings.internal_deadline_seconds),
    )
    latency_ms = int((time.monotonic() - request.state.started_at) * 1000)
    response = TaskAnalysisResponse(
        request_id=str(request.state.request_id),
        schema_version=SCHEMA_VERSION,
        status=inference.status,
        result=TaskAnalysisResult(
            **inference.output.model_dump(),
            language=language.language,
            primary_language=language.primary_language,
            original_text=body.text,
        ),
        trace=Trace(
            model_version=inference.model_version,
            prompt_version=PROMPT_VERSION,
            fallback_stage=inference.fallback_stage,
        ),
        latency_ms=latency_ms,
    )
    response_json = response.model_dump_json()
    pii_detected = await _persist_masked_event(
        request,
        body,
        response,
        inference,
        input_hash,
    )
    await request.app.state.idempotency.complete(
        idempotency_key,
        response_json,
        pii_detected=pii_detected,
    )
    return response
