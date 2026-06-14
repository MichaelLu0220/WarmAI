import time
from collections.abc import Callable
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int,
        recovery_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be positive")

        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.clock = clock
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self.half_open_probe_active = False

    def allow_request(self) -> bool:
        if self.state is CircuitState.CLOSED:
            return True
        if self.state is CircuitState.OPEN:
            if self.clock() - self.opened_at < self.recovery_seconds:
                return False
            self.state = CircuitState.HALF_OPEN
        if self.half_open_probe_active:
            return False
        self.half_open_probe_active = True
        return True

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.half_open_probe_active = False

    def record_failure(self) -> None:
        self.failures += 1
        self.half_open_probe_active = False
        if self.state is CircuitState.HALF_OPEN or self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = self.clock()
