import math
import time
from collections.abc import Callable
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Single-worker backend-availability circuit breaker.

    A half-open probe owns a lease for ``recovery_seconds``. The caller must
    abandon an expired probe before admitting its replacement and must not
    report stale outcomes from the abandoned operation.
    """

    __slots__ = (
        "_clock",
        "_failure_threshold",
        "_failures",
        "_half_open_probe_started_at",
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
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_probe_started_at: float | None = None

    @property
    def failure_threshold(self) -> int:
        return self._failure_threshold

    @property
    def recovery_seconds(self) -> float:
        return self._recovery_seconds

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow_request(self) -> bool:
        if self._state is CircuitState.CLOSED:
            return True
        now = self._clock()
        if self._state is CircuitState.OPEN:
            if now - self._opened_at < self._recovery_seconds:
                return False
            self._state = CircuitState.HALF_OPEN
            self._half_open_probe_started_at = now
            return True
        if (
            self._half_open_probe_started_at is not None
            and now - self._half_open_probe_started_at < self._recovery_seconds
        ):
            return False
        self._half_open_probe_started_at = now
        return True

    def record_success(self) -> None:
        if self._state is CircuitState.OPEN:
            raise RuntimeError("cannot record an outcome while circuit is open")
        if self._state is CircuitState.HALF_OPEN:
            self._require_active_half_open_probe(self._clock())
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._half_open_probe_started_at = None

    def record_failure(self) -> None:
        if self._state is CircuitState.OPEN:
            raise RuntimeError("cannot record an outcome while circuit is open")
        if self._state is CircuitState.HALF_OPEN:
            now = self._clock()
            self._require_active_half_open_probe(now)
            self._state = CircuitState.OPEN
            self._opened_at = now
            self._half_open_probe_started_at = None
            return

        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()
            self._half_open_probe_started_at = None

    def _require_active_half_open_probe(self, now: float) -> None:
        if (
            self._half_open_probe_started_at is None
            or now - self._half_open_probe_started_at >= self._recovery_seconds
        ):
            raise RuntimeError("half-open probe is not active")
