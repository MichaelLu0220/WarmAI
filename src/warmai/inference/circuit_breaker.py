import math
import time
from collections.abc import Callable
from dataclasses import InitVar, dataclass
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_PERMIT_CREATION_KEY = object()


@dataclass(frozen=True, slots=True, repr=False)
class AdmissionPermit:
    _admitted: bool
    _breaker_identity: object | None
    _probe_generation: int | None
    _creation_key: InitVar[object | None] = None

    def __post_init__(self, _creation_key: object | None) -> None:
        if _creation_key is not _PERMIT_CREATION_KEY:
            raise TypeError("AdmissionPermit cannot be constructed directly")

    def __bool__(self) -> bool:
        return self._admitted


_DENIED = AdmissionPermit(False, None, None, _PERMIT_CREATION_KEY)


class CircuitBreaker:
    """Single-worker backend-availability circuit breaker.

    ``allow_request`` returns a truth-testable permit. Closed-state outcomes
    may be recorded without it. When supplied, an outcome permit must be the
    exact active object so copied, foreign, consumed, and stale permits fail.
    """

    __slots__ = (
        "_active_permit",
        "_active_probe_generation",
        "_breaker_identity",
        "_clock",
        "_failure_threshold",
        "_failures",
        "_half_open_probe_started_at",
        "_next_probe_generation",
        "_opened_at",
        "_recovery_seconds",
        "_state",
    )

    def __init__(
        self,
        failure_threshold: int,
        recovery_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if not math.isfinite(recovery_seconds) or recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be finite and positive")

        self._failure_threshold = failure_threshold
        self._recovery_seconds = recovery_seconds
        self._clock = clock
        self._breaker_identity = object()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_probe_started_at: float | None = None
        self._active_permit: AdmissionPermit | None = None
        self._active_probe_generation: int | None = None
        self._next_probe_generation = 0

    @property
    def failure_threshold(self) -> int:
        return self._failure_threshold

    @property
    def recovery_seconds(self) -> float:
        return self._recovery_seconds

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow_request(self) -> AdmissionPermit:
        if self._state is CircuitState.CLOSED:
            permit = AdmissionPermit(
                True,
                self._breaker_identity,
                None,
                _PERMIT_CREATION_KEY,
            )
            self._active_permit = permit
            return permit
        now = self._read_clock()
        if self._state is CircuitState.OPEN:
            if now - self._opened_at < self._recovery_seconds:
                return _DENIED
            self._state = CircuitState.HALF_OPEN
            return self._admit_half_open_probe(now)
        if (
            self._half_open_probe_started_at is not None
            and now - self._half_open_probe_started_at < self._recovery_seconds
        ):
            return _DENIED
        return self._admit_half_open_probe(now)

    def record_success(self, permit: AdmissionPermit | None = None) -> None:
        if self._state is CircuitState.OPEN:
            raise RuntimeError("cannot record an outcome while circuit is open")
        if self._state is CircuitState.HALF_OPEN:
            self._require_active_half_open_permit(permit, self._read_clock())
        elif permit is not None:
            self._validate_closed_permit(permit)
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._clear_active_admission()

    def record_failure(self, permit: AdmissionPermit | None = None) -> None:
        if self._state is CircuitState.OPEN:
            raise RuntimeError("cannot record an outcome while circuit is open")
        if self._state is CircuitState.HALF_OPEN:
            now = self._read_clock()
            self._require_active_half_open_permit(permit, now)
            self._state = CircuitState.OPEN
            self._opened_at = now
            self._clear_active_admission()
            return
        if permit is not None:
            self._validate_closed_permit(permit)

        next_failures = self._failures + 1
        if next_failures >= self._failure_threshold:
            now = self._read_clock()
            self._failures = next_failures
            self._state = CircuitState.OPEN
            self._opened_at = now
            self._clear_active_admission()
            return
        self._failures = next_failures
        self._clear_active_admission()

    def _admit_half_open_probe(self, now: float) -> AdmissionPermit:
        self._next_probe_generation += 1
        self._active_probe_generation = self._next_probe_generation
        self._half_open_probe_started_at = now
        permit = AdmissionPermit(
            True,
            self._breaker_identity,
            self._active_probe_generation,
            _PERMIT_CREATION_KEY,
        )
        self._active_permit = permit
        return permit

    def _clear_active_admission(self) -> None:
        self._active_permit = None
        self._active_probe_generation = None
        self._half_open_probe_started_at = None

    def _require_active_half_open_permit(
        self,
        permit: AdmissionPermit | None,
        now: float,
    ) -> None:
        if not isinstance(permit, AdmissionPermit) or not permit:
            raise RuntimeError("valid half-open permit is required")
        if permit._breaker_identity is not self._breaker_identity:
            raise RuntimeError("permit belongs to a different circuit breaker")
        if (
            self._half_open_probe_started_at is None
            or now - self._half_open_probe_started_at >= self._recovery_seconds
        ):
            raise RuntimeError("half-open probe is not active")
        if permit is not self._active_permit:
            raise RuntimeError("permit does not match active half-open probe")
        if permit._probe_generation != self._active_probe_generation:
            raise RuntimeError("permit does not match active half-open probe")

    def _validate_closed_permit(self, permit: AdmissionPermit) -> None:
        if not isinstance(permit, AdmissionPermit) or not permit:
            raise RuntimeError("admitted permit is required")
        if permit._breaker_identity is not self._breaker_identity:
            raise RuntimeError("permit belongs to a different circuit breaker")
        if permit is not self._active_permit:
            if permit._probe_generation is not None:
                raise RuntimeError("half-open permit is no longer active")
            raise RuntimeError("permit is no longer active")
        if permit._probe_generation is not None:
            raise RuntimeError("half-open permit is no longer active")

    def _read_clock(self) -> float:
        value = self._clock()
        if not math.isfinite(value):
            raise ValueError("clock reading must be finite")
        return value
