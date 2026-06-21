import asyncio
from typing import Any

import pytest

from warmai.config.model_config import MAX_RETRY, PROMPT_VERSION
from warmai.contracts.common import FallbackStage, PrimaryLanguage, ResponseStatus
from warmai.contracts.task_analysis import ModelOutput
from warmai.inference.adapters.base import AdapterAvailabilityError, AdapterResponse
from warmai.inference.adapters.mock import MockAdapter
from warmai.inference.circuit_breaker import CircuitBreaker
from warmai.inference.deadline import Deadline
from warmai.inference.prompt import build_prompt
from warmai.inference.service import InferenceService


@pytest.mark.asyncio
async def test_valid_first_response_is_ok() -> None:
    adapter = MockAdapter()
    service = InferenceService(adapter, CircuitBreaker(3, 30))

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(4.5),
    )

    assert result.status is ResponseStatus.OK
    assert result.fallback_stage is FallbackStage.NONE
    assert result.validation_result == "valid"
    assert result.recovered_fields == []
    assert result.defaulted_fields == []
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_json_repair_response_is_ok() -> None:
    adapter = MockAdapter(
        outputs=[
            (
                '{"suggested_text":null,"score":3,'
                '"correction_confidence":0.9,"score_confidence":0.6,'
                '"warnings":[],"reason":"Several steps.","needs_review":false,}'
            )
        ],
    )
    service = InferenceService(adapter, CircuitBreaker(3, 30))

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(4.5),
    )

    assert result.status is ResponseStatus.OK
    assert result.fallback_stage is FallbackStage.JSON_REPAIR
    assert result.validation_result == "repaired"
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_retry_occurs_at_most_once() -> None:
    adapter = MockAdapter(outputs=["not json", "still not json"])
    service = InferenceService(adapter, CircuitBreaker(3, 30))

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(4.5),
    )

    assert adapter.calls == MAX_RETRY + 1
    assert result.fallback_stage is FallbackStage.SAFE_DEFAULT
    assert result.output.needs_review is True
    assert result.defaulted_fields == list(ModelOutput.model_fields)


@pytest.mark.asyncio
async def test_partial_response_is_used_after_retry_budget() -> None:
    adapter = MockAdapter(outputs=['{"score":87,"reason":"Several steps."}'])
    service = InferenceService(adapter, CircuitBreaker(3, 30))

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(0.5),
    )

    assert adapter.calls == 1
    assert result.status is ResponseStatus.DEGRADED
    assert result.fallback_stage is FallbackStage.PARTIAL
    assert result.validation_result == "partial"
    assert result.output.score == 3
    assert result.output.reason == "Several steps."
    assert result.recovered_fields == ["reason"]
    assert "score" in result.defaulted_fields


class ConcurrencyAdapter:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def generate(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> AdapterResponse:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return AdapterResponse(
            raw_text=(
                '{"suggested_text":null,"score":3,'
                '"correction_confidence":0.9,"score_confidence":0.6,'
                '"warnings":[],"reason":"Several steps.","needs_review":false}'
            ),
            model_version="concurrency-test",
        )

    async def healthcheck(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_service_serializes_model_requests() -> None:
    adapter = ConcurrencyAdapter()
    service = InferenceService(adapter, CircuitBreaker(3, 30))

    await asyncio.gather(
        service.analyze(
            text="Clean the room",
            primary_language=PrimaryLanguage.EN,
            deadline=Deadline.after(4.5),
        ),
        service.analyze(
            text="Clean the desk",
            primary_language=PrimaryLanguage.EN,
            deadline=Deadline.after(4.5),
        ),
    )

    assert adapter.max_active == 1


class UnavailableAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> AdapterResponse:
        self.calls += 1
        raise AdapterAvailabilityError("backend unavailable")

    async def healthcheck(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_adapter_availability_error_uses_safe_default() -> None:
    adapter = UnavailableAdapter()
    service = InferenceService(adapter, CircuitBreaker(3, 30))

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(4.5),
    )

    assert adapter.calls == MAX_RETRY + 1
    assert result.status is ResponseStatus.DEGRADED
    assert result.fallback_stage is FallbackStage.SAFE_DEFAULT
    assert result.validation_result == "backend unavailable"
    assert result.model_version == "unavailable"


@pytest.mark.asyncio
async def test_adapter_failure_that_opens_circuit_reports_adapter_error() -> None:
    adapter = UnavailableAdapter()
    service = InferenceService(adapter, CircuitBreaker(1, 30))

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(4.5),
    )

    assert adapter.calls == 1
    assert result.fallback_stage is FallbackStage.SAFE_DEFAULT
    assert result.validation_result == "backend unavailable"


@pytest.mark.asyncio
async def test_open_circuit_returns_safe_default_without_adapter_call() -> None:
    adapter = MockAdapter()
    breaker = CircuitBreaker(1, 30)
    permit = breaker.allow_request()
    breaker.record_failure(permit)
    service = InferenceService(adapter, breaker)

    result = await service.analyze(
        text="Clean the room",
        primary_language=PrimaryLanguage.EN,
        deadline=Deadline.after(4.5),
    )

    assert adapter.calls == 0
    assert result.status is ResponseStatus.DEGRADED
    assert result.fallback_stage is FallbackStage.SAFE_DEFAULT
    assert result.validation_result == "circuit_open"


def test_build_prompt_includes_version_language_task_and_retry_note() -> None:
    prompt = build_prompt(
        "Clean the room",
        PrimaryLanguage.EN,
        validation_error="score must be <= 5",
    )

    assert PROMPT_VERSION == "task-analysis-002"
    assert "Prompt version: task-analysis-002" in prompt
    assert "/no_think" in prompt
    assert "Give one reason in en" in prompt
    assert "Score 1: trivial, one clear step, usually under 5 minutes." in prompt
    assert "Score 3: normal chore or personal task with multiple steps" in prompt
    assert "Score 4: substantial task needing planning" in prompt
    assert "suggested_text must be null" in prompt
    assert "Do not rewrite clear text just to make it prettier" in prompt
    assert "score must be <= 5" in prompt
    assert prompt.endswith("Task: Clean the room")


def test_build_prompt_can_load_prior_template_version() -> None:
    prompt = build_prompt(
        "Clean the room",
        PrimaryLanguage.EN,
        prompt_version="task-analysis-001",
    )

    assert "Prompt version: task-analysis-001" in prompt
    assert "Only correct clear spelling, typo, or grammar errors." in prompt
    assert "Score 1: trivial" not in prompt


def test_build_prompt_rejects_unknown_template_version() -> None:
    with pytest.raises(ValueError, match="Unknown prompt template version"):
        build_prompt(
            "Clean the room",
            PrimaryLanguage.EN,
            prompt_version="task-analysis-999",
        )
