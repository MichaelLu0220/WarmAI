from dataclasses import FrozenInstanceError

import pytest

from warmai.inference.adapters.base import (
    AdapterAvailabilityError,
    AdapterResponse,
    InferenceAdapter,
)
from warmai.inference.adapters.mock import MockAdapter
from warmai.inference.circuit_breaker import CircuitBreaker, CircuitState

DEFAULT_MOCK_OUTPUT = (
    '{"suggested_text":null,"score":3,'
    '"correction_confidence":0.9,"score_confidence":0.6,'
    '"warnings":[],"reason":"Mock analysis.","needs_review":false}'
)


def assert_breaker_state(breaker: CircuitBreaker, expected: CircuitState) -> None:
    assert breaker.state is expected


def test_breaker_opens_at_configured_failure_threshold() -> None:
    breaker = CircuitBreaker(3, 30.0, clock=lambda: 100.0)

    breaker.record_failure()
    breaker.record_failure()

    assert_breaker_state(breaker, CircuitState.CLOSED)
    assert breaker.allow_request()

    breaker.record_failure()

    assert_breaker_state(breaker, CircuitState.OPEN)
    assert not breaker.allow_request()


def test_open_breaker_rejects_requests_before_recovery_interval() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()

    now[0] = 129.999

    assert not breaker.allow_request()
    assert_breaker_state(breaker, CircuitState.OPEN)


def test_recovered_breaker_permits_exactly_one_half_open_probe() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0

    assert breaker.allow_request()
    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    assert not breaker.allow_request()


def test_successful_half_open_probe_closes_and_resets_breaker() -> None:
    now = [100.0]
    breaker = CircuitBreaker(3, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    now[0] = 130.0
    assert breaker.allow_request()

    breaker.record_success()

    assert_breaker_state(breaker, CircuitState.CLOSED)
    assert breaker.allow_request()
    breaker.record_failure()
    breaker.record_failure()
    assert_breaker_state(breaker, CircuitState.CLOSED)
    breaker.record_failure()
    assert_breaker_state(breaker, CircuitState.OPEN)


def test_failed_half_open_probe_reopens_and_restarts_recovery() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    assert breaker.allow_request()

    now[0] = 135.0
    breaker.record_failure()

    assert_breaker_state(breaker, CircuitState.OPEN)
    now[0] = 164.999
    assert not breaker.allow_request()
    now[0] = 165.0
    assert breaker.allow_request()
    assert_breaker_state(breaker, CircuitState.HALF_OPEN)


@pytest.mark.parametrize(
    ("failure_threshold", "recovery_seconds", "message"),
    [
        (0, 30.0, "failure_threshold must be positive"),
        (-1, 30.0, "failure_threshold must be positive"),
        (3, 0.0, "recovery_seconds must be positive"),
        (3, -0.1, "recovery_seconds must be positive"),
    ],
)
def test_breaker_rejects_non_positive_configuration(
    failure_threshold: int,
    recovery_seconds: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CircuitBreaker(failure_threshold, recovery_seconds)


def test_adapter_contract_types_are_runtime_compatible_and_immutable() -> None:
    adapter: InferenceAdapter = MockAdapter()
    response = AdapterResponse(raw_text="{}", model_version="test-001")

    assert isinstance(adapter, InferenceAdapter)
    assert issubclass(AdapterAvailabilityError, RuntimeError)
    with pytest.raises(FrozenInstanceError):
        response.raw_text = "changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_mock_adapter_consumes_queued_outputs_before_default() -> None:
    adapter = MockAdapter(outputs=["first", "second"])

    responses = [
        await adapter.generate(prompt="one", json_schema={}, timeout_seconds=1.0),
        await adapter.generate(prompt="two", json_schema={}, timeout_seconds=1.0),
        await adapter.generate(prompt="three", json_schema={}, timeout_seconds=1.0),
    ]

    assert [response.raw_text for response in responses] == [
        "first",
        "second",
        DEFAULT_MOCK_OUTPUT,
    ]
    assert [response.model_version for response in responses] == ["mock-001"] * 3
    assert adapter.calls == 3


@pytest.mark.asyncio
async def test_mock_adapter_healthcheck_is_healthy() -> None:
    assert await MockAdapter().healthcheck() is True
