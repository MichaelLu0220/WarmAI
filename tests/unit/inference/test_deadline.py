import pytest

from warmai.inference.deadline import Deadline


@pytest.mark.parametrize("expires_at", [float("nan"), float("inf"), float("-inf")])
def test_deadline_rejects_non_finite_direct_expiry(expires_at: float) -> None:
    with pytest.raises(ValueError, match="expires_at must be finite"):
        Deadline(expires_at)


def test_deadline_uses_remaining_shared_budget() -> None:
    values = iter([10.0, 11.25])

    deadline = Deadline.after(4.5, clock=lambda: next(values))

    assert deadline.remaining() == 3.25


def test_deadline_remaining_is_clamped_to_zero_after_exhaustion() -> None:
    now = [10.0]
    deadline = Deadline.after(1.0, clock=lambda: now[0])

    now[0] = 11.5

    assert deadline.remaining() == 0.0


def test_deadline_has_required_remaining_budget() -> None:
    now = [10.0]
    deadline = Deadline.after(4.5, clock=lambda: now[0])

    now[0] = 13.0

    assert deadline.has(1.5)
    assert not deadline.has(1.500001)


@pytest.mark.parametrize("seconds", [0.0, -0.1, float("nan"), float("inf"), float("-inf")])
def test_deadline_rejects_invalid_duration(seconds: float) -> None:
    with pytest.raises(ValueError, match="seconds must be finite and positive"):
        Deadline.after(seconds)


@pytest.mark.parametrize(
    "minimum_seconds",
    [-0.1, float("nan"), float("inf"), float("-inf")],
)
def test_deadline_has_rejects_invalid_minimum(minimum_seconds: float) -> None:
    deadline = Deadline.after(1.0, clock=lambda: 10.0)

    with pytest.raises(ValueError, match="minimum_seconds must be finite and non-negative"):
        deadline.has(minimum_seconds)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), float("-inf")])
def test_deadline_after_rejects_non_finite_clock_reading(clock_value: float) -> None:
    with pytest.raises(ValueError, match="clock reading must be finite"):
        Deadline.after(1.0, clock=lambda: clock_value)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), float("-inf")])
def test_deadline_remaining_rejects_non_finite_clock_reading(clock_value: float) -> None:
    deadline = Deadline(11.0, clock=lambda: clock_value)

    with pytest.raises(ValueError, match="clock reading must be finite"):
        deadline.remaining()
