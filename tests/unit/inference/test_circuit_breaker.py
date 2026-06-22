from copy import copy, deepcopy
from dataclasses import FrozenInstanceError

import pytest

from warmai.inference.adapters.base import (
    AdapterAvailabilityError,
    AdapterResponse,
    InferenceAdapter,
)
from warmai.inference.adapters.mock import MockAdapter
from warmai.inference.circuit_breaker import AdmissionPermit, CircuitBreaker, CircuitState

DEFAULT_MOCK_OUTPUT = (
    '{"suggested_text":null,"score":3,'
    '"correction_confidence":0.9,"score_confidence":0.6,'
    '"warnings":[],"reason":"Mock analysis.",'
    '"is_task":true,"needs_review":false}'
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

    permit = breaker.allow_request()

    assert permit
    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    assert not breaker.allow_request()


def test_abandoned_half_open_probe_is_replaced_after_lease_expires() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit_a = breaker.allow_request()
    assert permit_a

    now[0] = 159.999
    assert not breaker.allow_request()
    now[0] = 160.0
    permit_b = breaker.allow_request()
    assert permit_b
    assert not breaker.allow_request()

    with pytest.raises(RuntimeError, match="permit does not match active half-open probe"):
        breaker.record_success(permit_a)

    breaker.record_success(permit_b)
    assert_breaker_state(breaker, CircuitState.CLOSED)


def test_successful_half_open_probe_closes_and_resets_breaker() -> None:
    now = [100.0]
    breaker = CircuitBreaker(3, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    assert permit

    breaker.record_success(permit)

    assert_breaker_state(breaker, CircuitState.CLOSED)
    assert breaker.allow_request()
    breaker.record_failure()
    breaker.record_failure()
    assert_breaker_state(breaker, CircuitState.CLOSED)
    breaker.record_failure()
    assert_breaker_state(breaker, CircuitState.OPEN)


def test_success_in_closed_state_resets_consecutive_failures() -> None:
    breaker = CircuitBreaker(3, 30.0, clock=lambda: 100.0)
    breaker.record_failure()
    breaker.record_failure()

    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()

    assert_breaker_state(breaker, CircuitState.CLOSED)


def test_closed_success_accepts_matching_admission_permit_and_resets_failures() -> None:
    breaker = CircuitBreaker(3, 30.0, clock=lambda: 100.0)
    breaker.record_failure(breaker.allow_request())
    breaker.record_failure(breaker.allow_request())

    permit = breaker.allow_request()
    breaker.record_success(permit)

    breaker.record_failure(breaker.allow_request())
    breaker.record_failure(breaker.allow_request())
    assert_breaker_state(breaker, CircuitState.CLOSED)
    breaker.record_failure(breaker.allow_request())
    assert_breaker_state(breaker, CircuitState.OPEN)


def test_closed_failure_accepts_matching_admission_permit_and_opens_at_threshold() -> None:
    breaker = CircuitBreaker(2, 30.0, clock=lambda: 100.0)

    breaker.record_failure(breaker.allow_request())

    assert_breaker_state(breaker, CircuitState.CLOSED)
    breaker.record_failure(breaker.allow_request())
    assert_breaker_state(breaker, CircuitState.OPEN)


@pytest.mark.parametrize("outcome", ["record_success", "record_failure"])
def test_closed_permit_is_consumed_after_one_outcome(outcome: str) -> None:
    breaker = CircuitBreaker(3, 30.0, clock=lambda: 100.0)
    permit = breaker.allow_request()

    getattr(breaker, outcome)(permit)

    with pytest.raises(RuntimeError):
        getattr(breaker, outcome)(permit)

    assert_breaker_state(breaker, CircuitState.CLOSED)


def test_closed_permitless_outcome_consumes_active_permit() -> None:
    breaker = CircuitBreaker(3, 30.0, clock=lambda: 100.0)
    permit = breaker.allow_request()

    breaker.record_success()

    with pytest.raises(RuntimeError):
        breaker.record_success(permit)

    assert_breaker_state(breaker, CircuitState.CLOSED)


def test_latest_closed_permit_is_the_only_active_admission() -> None:
    breaker = CircuitBreaker(3, 30.0, clock=lambda: 100.0)
    stale_permit = breaker.allow_request()
    active_permit = breaker.allow_request()

    with pytest.raises(RuntimeError):
        breaker.record_success(stale_permit)

    breaker.record_success(active_permit)
    assert_breaker_state(breaker, CircuitState.CLOSED)


@pytest.mark.parametrize("use_deepcopy", [False, True], ids=["copy", "deepcopy"])
@pytest.mark.parametrize("half_open", [False, True], ids=["closed", "half-open"])
def test_copied_permit_cannot_report_an_outcome(
    use_deepcopy: bool,
    half_open: bool,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1 if half_open else 3, 30.0, clock=lambda: now[0])
    if half_open:
        breaker.record_failure()
        now[0] = 130.0
    permit = breaker.allow_request()
    copied_permit = (
        deepcopy(permit, {id(permit._breaker_identity): permit._breaker_identity})
        if use_deepcopy
        else copy(permit)
    )

    assert copied_permit is not permit
    with pytest.raises(RuntimeError):
        breaker.record_success(copied_permit)

    breaker.record_success(permit)
    assert_breaker_state(breaker, CircuitState.CLOSED)


@pytest.mark.parametrize("outcome", ["record_success", "record_failure"])
def test_closed_outcome_rejects_permit_from_another_breaker(outcome: str) -> None:
    first = CircuitBreaker(3, 30.0)
    second = CircuitBreaker(3, 30.0)
    foreign_permit = first.allow_request()

    with pytest.raises(RuntimeError, match="permit belongs to a different circuit breaker"):
        getattr(second, outcome)(foreign_permit)

    assert_breaker_state(second, CircuitState.CLOSED)


@pytest.mark.parametrize("outcome", ["record_success", "record_failure"])
def test_closed_outcome_rejects_denied_permit(outcome: str) -> None:
    source = CircuitBreaker(1, 30.0, clock=lambda: 100.0)
    source.record_failure()
    denied = source.allow_request()
    target = CircuitBreaker(3, 30.0)

    assert not denied
    with pytest.raises(RuntimeError, match="admitted permit is required"):
        getattr(target, outcome)(denied)

    assert_breaker_state(target, CircuitState.CLOSED)


def test_failed_half_open_probe_reopens_and_restarts_recovery() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    assert permit

    now[0] = 135.0
    breaker.record_failure(permit)

    assert_breaker_state(breaker, CircuitState.OPEN)
    now[0] = 164.999
    assert not breaker.allow_request()
    now[0] = 165.0
    assert breaker.allow_request()
    assert_breaker_state(breaker, CircuitState.HALF_OPEN)


@pytest.mark.parametrize("outcome", ["record_success", "record_failure"])
def test_outcome_reported_while_open_is_rejected_without_changing_recovery(
    outcome: str,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 110.0

    with pytest.raises(RuntimeError, match="cannot record an outcome while circuit is open"):
        getattr(breaker, outcome)()

    assert_breaker_state(breaker, CircuitState.OPEN)
    now[0] = 129.999
    assert not breaker.allow_request()
    now[0] = 130.0
    assert breaker.allow_request()


@pytest.mark.parametrize("outcome", ["record_success", "record_failure"])
def test_half_open_outcome_requires_an_unexpired_admitted_probe(outcome: str) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    assert permit
    now[0] = 160.0

    with pytest.raises(RuntimeError, match="half-open probe is not active"):
        getattr(breaker, outcome)(permit)

    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    assert breaker.allow_request()


@pytest.mark.parametrize(
    ("outcome", "expected_state"),
    [
        ("record_success", CircuitState.CLOSED),
        ("record_failure", CircuitState.OPEN),
    ],
)
def test_stale_probe_outcome_cannot_complete_replacement_probe(
    outcome: str,
    expected_state: CircuitState,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit_a = breaker.allow_request()
    assert permit_a

    now[0] = 160.0
    permit_b = breaker.allow_request()
    assert permit_b

    with pytest.raises(RuntimeError, match="permit does not match active half-open probe"):
        getattr(breaker, outcome)(permit_a)

    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    assert not breaker.allow_request()

    getattr(breaker, outcome)(permit_b)

    assert_breaker_state(breaker, expected_state)


def test_half_open_rejects_permit_from_another_breaker() -> None:
    now = [100.0]
    first = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    second = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    first.record_failure()
    second.record_failure()
    now[0] = 130.0
    first_permit = first.allow_request()
    second_permit = second.allow_request()
    assert first_permit
    assert second_permit

    with pytest.raises(RuntimeError, match="permit belongs to a different circuit breaker"):
        second.record_success(first_permit)

    assert_breaker_state(second, CircuitState.HALF_OPEN)
    second.record_success(second_permit)
    assert_breaker_state(second, CircuitState.CLOSED)


def test_consumed_half_open_permit_cannot_be_reused() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    assert permit
    breaker.record_success(permit)

    with pytest.raises(RuntimeError, match="half-open permit is no longer active"):
        breaker.record_success(permit)

    assert_breaker_state(breaker, CircuitState.CLOSED)


@pytest.mark.parametrize("outcome", ["record_success", "record_failure"])
def test_half_open_rejects_bare_boolean_as_permit(outcome: str) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    assert permit

    with pytest.raises(RuntimeError, match="valid half-open permit is required"):
        getattr(breaker, outcome)(True)

    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    getattr(breaker, outcome)(permit)


def test_admission_permits_preserve_boolean_request_checks() -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])

    assert breaker.allow_request()
    breaker.record_failure()

    denied = breaker.allow_request()

    assert not denied
    assert isinstance(denied, AdmissionPermit)


def test_admission_permits_are_immutable_and_not_directly_constructible() -> None:
    permit = CircuitBreaker(1, 30.0).allow_request()

    with pytest.raises(FrozenInstanceError):
        permit._admitted = False  # type: ignore[misc]
    with pytest.raises(TypeError, match="AdmissionPermit cannot be constructed directly"):
        AdmissionPermit(True, object(), 1)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), float("-inf")])
def test_open_admission_rejects_non_finite_clock_without_mutating_state(
    clock_value: float,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = clock_value

    with pytest.raises(ValueError, match="clock reading must be finite"):
        breaker.allow_request()

    assert_breaker_state(breaker, CircuitState.OPEN)
    now[0] = 130.0
    assert breaker.allow_request()
    assert_breaker_state(breaker, CircuitState.HALF_OPEN)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), float("-inf")])
def test_half_open_lease_rejects_non_finite_clock_without_replacing_probe(
    clock_value: float,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    now[0] = clock_value

    with pytest.raises(ValueError, match="clock reading must be finite"):
        breaker.allow_request()

    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    now[0] = 135.0
    breaker.record_success(permit)
    assert_breaker_state(breaker, CircuitState.CLOSED)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    ("outcome", "expected_state"),
    [
        ("record_success", CircuitState.CLOSED),
        ("record_failure", CircuitState.OPEN),
    ],
)
def test_half_open_outcome_rejects_non_finite_clock_without_consuming_probe(
    clock_value: float,
    outcome: str,
    expected_state: CircuitState,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(1, 30.0, clock=lambda: now[0])
    breaker.record_failure()
    now[0] = 130.0
    permit = breaker.allow_request()
    now[0] = clock_value

    with pytest.raises(ValueError, match="clock reading must be finite"):
        getattr(breaker, outcome)(permit)

    assert_breaker_state(breaker, CircuitState.HALF_OPEN)
    now[0] = 135.0
    getattr(breaker, outcome)(permit)
    assert_breaker_state(breaker, expected_state)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), float("-inf")])
def test_threshold_failure_rejects_non_finite_clock_before_mutating_state_or_count(
    clock_value: float,
) -> None:
    now = [100.0]
    breaker = CircuitBreaker(3, 30.0, clock=lambda: now[0])
    breaker.record_failure(breaker.allow_request())
    breaker.record_failure(breaker.allow_request())
    permit = breaker.allow_request()
    now[0] = clock_value

    with pytest.raises(ValueError, match="clock reading must be finite"):
        breaker.record_failure(permit)

    assert_breaker_state(breaker, CircuitState.CLOSED)
    now[0] = 100.0
    breaker.record_failure(permit)
    assert_breaker_state(breaker, CircuitState.OPEN)


@pytest.mark.parametrize(
    ("failure_threshold", "recovery_seconds", "message"),
    [
        (0, 30.0, "failure_threshold must be positive"),
        (-1, 30.0, "failure_threshold must be positive"),
        (3, 0.0, "recovery_seconds must be finite and positive"),
        (3, -0.1, "recovery_seconds must be finite and positive"),
        (3, float("nan"), "recovery_seconds must be finite and positive"),
        (3, float("inf"), "recovery_seconds must be finite and positive"),
        (3, float("-inf"), "recovery_seconds must be finite and positive"),
    ],
)
def test_breaker_rejects_non_positive_configuration(
    failure_threshold: int,
    recovery_seconds: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CircuitBreaker(failure_threshold, recovery_seconds)


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("state", CircuitState.OPEN),
        ("failure_threshold", 1),
        ("recovery_seconds", 1.0),
    ],
)
def test_breaker_public_configuration_and_state_are_read_only(
    attribute: str,
    value: object,
) -> None:
    breaker = CircuitBreaker(3, 30.0)

    with pytest.raises(AttributeError):
        setattr(breaker, attribute, value)

    assert breaker.state is CircuitState.CLOSED
    assert breaker.failure_threshold == 3
    assert breaker.recovery_seconds == 30.0


def test_adapter_response_is_immutable_and_availability_error_is_runtime_error() -> None:
    response = AdapterResponse(raw_text="{}", model_version="test-001")

    assert issubclass(AdapterAvailabilityError, RuntimeError)
    with pytest.raises(FrozenInstanceError):
        response.raw_text = "changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_mock_adapter_consumes_queued_outputs_before_default() -> None:
    mock = MockAdapter(outputs=["first", "second"])
    adapter: InferenceAdapter = mock

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
    assert mock.calls == 3


@pytest.mark.asyncio
async def test_mock_adapter_healthcheck_is_healthy() -> None:
    adapter: InferenceAdapter = MockAdapter()

    assert await adapter.healthcheck() is True
