import logging
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from warmai.config.model_config import SCHEMA_VERSION
from warmai.contracts.common import ResponseStatus
from warmai.contracts.errors import ErrorCode, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiProblem(Exception):
    status_code: int
    code: ErrorCode
    message: str
    retryable: bool = False


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def handle_problem(request: Request, error: ApiProblem) -> JSONResponse:
        started = getattr(request.state, "started_at", time.monotonic())
        body = ErrorResponse(
            request_id=str(getattr(request.state, "request_id", uuid4())),
            schema_version=SCHEMA_VERSION,
            status=ResponseStatus.ERROR,
            error=ErrorDetail(
                code=error.code,
                message=error.message,
                retryable=error.retryable,
            ),
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        return JSONResponse(
            status_code=error.status_code,
            content=body.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        problem = ApiProblem(
            400,
            ErrorCode.INVALID_INPUT,
            "Request body and headers must match the v1 contract.",
        )
        return await handle_problem(request, problem)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.exception("unhandled service error")
        return await handle_problem(
            request,
            ApiProblem(
                503,
                ErrorCode.SERVICE_UNAVAILABLE,
                "WarmAI could not create a valid response.",
                retryable=True,
            ),
        )
