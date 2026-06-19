import asyncio
import json
from dataclasses import dataclass

from pydantic import ValidationError

from warmai.config.model_config import MAX_RETRY
from warmai.contracts.common import FallbackStage, PrimaryLanguage, ResponseStatus
from warmai.contracts.task_analysis import ModelOutput
from warmai.inference.adapters.base import AdapterAvailabilityError, InferenceAdapter
from warmai.inference.circuit_breaker import CircuitBreaker
from warmai.inference.deadline import Deadline
from warmai.inference.prompt import build_prompt
from warmai.recovery.json_repair import repair_json_syntax
from warmai.recovery.partial import recover_partial, safe_default


@dataclass(frozen=True)
class InferenceResult:
    output: ModelOutput
    raw_model_output: str
    model_version: str
    status: ResponseStatus
    fallback_stage: FallbackStage
    validation_result: str
    recovered_fields: list[str]
    defaulted_fields: list[str]


class InferenceService:
    def __init__(self, adapter: InferenceAdapter, breaker: CircuitBreaker) -> None:
        self.adapter = adapter
        self.breaker = breaker
        self._inference_lock = asyncio.Lock()

    async def analyze(
        self,
        *,
        text: str,
        primary_language: PrimaryLanguage,
        deadline: Deadline,
    ) -> InferenceResult:
        async with self._inference_lock:
            return await self._analyze_locked(
                text=text,
                primary_language=primary_language,
                deadline=deadline,
            )

    async def _analyze_locked(
        self,
        *,
        text: str,
        primary_language: PrimaryLanguage,
        deadline: Deadline,
    ) -> InferenceResult:
        last_raw = ""
        last_error = ""
        retrying_after_adapter_failure = False

        for attempts in range(MAX_RETRY + 1):
            if not deadline.has(0.25):
                break

            permit = self.breaker.allow_request()
            if not permit:
                validation_result = (
                    last_error if retrying_after_adapter_failure and last_error else "circuit_open"
                )
                return self._safe(primary_language, validation_result, last_raw)
            retrying_after_adapter_failure = False

            prompt = build_prompt(text, primary_language, last_error or None)
            try:
                response = await self.adapter.generate(
                    prompt=prompt,
                    json_schema=ModelOutput.model_json_schema(),
                    timeout_seconds=deadline.remaining(),
                )
                self.breaker.record_success(permit)
            except AdapterAvailabilityError as error:
                self.breaker.record_failure(permit)
                last_error = str(error)
                if attempts < MAX_RETRY and deadline.has(0.75):
                    retrying_after_adapter_failure = True
                    continue
                return self._safe(primary_language, last_error, last_raw)

            last_raw = response.raw_text
            direct = self._validate(last_raw)
            if direct is not None:
                stage = FallbackStage.NONE if attempts == 0 else FallbackStage.RETRY
                status = ResponseStatus.OK if attempts == 0 else ResponseStatus.DEGRADED
                return InferenceResult(
                    direct,
                    last_raw,
                    response.model_version,
                    status,
                    stage,
                    "valid",
                    [],
                    [],
                )

            repaired_text = repair_json_syntax(last_raw)
            repaired = self._validate(repaired_text)
            if repaired is not None:
                stage = FallbackStage.JSON_REPAIR if attempts == 0 else FallbackStage.RETRY
                status = ResponseStatus.OK if attempts == 0 else ResponseStatus.DEGRADED
                return InferenceResult(
                    repaired,
                    last_raw,
                    response.model_version,
                    status,
                    stage,
                    "repaired",
                    [],
                    [],
                )

            try:
                parsed = json.loads(repaired_text)
            except json.JSONDecodeError as error:
                last_error = str(error)
            else:
                if isinstance(parsed, dict):
                    partial = recover_partial(parsed, primary_language)
                    last_error = "model output failed validation"
                    if not deadline.has(0.75) or attempts == MAX_RETRY:
                        return InferenceResult(
                            partial.output,
                            last_raw,
                            response.model_version,
                            ResponseStatus.DEGRADED,
                            FallbackStage.PARTIAL,
                            "partial",
                            partial.recovered_fields,
                            partial.defaulted_fields,
                        )
                else:
                    last_error = "model output is not a JSON object"

        return self._safe(primary_language, last_error, last_raw)

    @staticmethod
    def _validate(raw: str) -> ModelOutput | None:
        try:
            return ModelOutput.model_validate_json(raw)
        except ValidationError:
            return None

    @staticmethod
    def _safe(
        language: PrimaryLanguage,
        validation_result: str,
        raw: str = "",
    ) -> InferenceResult:
        return InferenceResult(
            safe_default(language),
            raw,
            "unavailable",
            ResponseStatus.DEGRADED,
            FallbackStage.SAFE_DEFAULT,
            validation_result,
            [],
            list(ModelOutput.model_fields),
        )
