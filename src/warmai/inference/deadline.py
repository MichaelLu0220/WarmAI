import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Deadline:
    expires_at: float
    clock: Callable[[], float] = time.monotonic

    @classmethod
    def after(
        cls,
        seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> "Deadline":
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        return cls(clock() + seconds, clock)

    def remaining(self) -> float:
        return max(0.0, self.expires_at - self.clock())

    def has(self, minimum_seconds: float) -> bool:
        return self.remaining() >= minimum_seconds
