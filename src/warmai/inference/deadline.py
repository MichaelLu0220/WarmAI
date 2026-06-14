import math
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Deadline:
    expires_at: float
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        if not math.isfinite(self.expires_at):
            raise ValueError("expires_at must be finite")

    @classmethod
    def after(
        cls,
        seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> "Deadline":
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("seconds must be finite and positive")
        return cls(_read_clock(clock) + seconds, clock)

    def remaining(self) -> float:
        remaining = self.expires_at - _read_clock(self.clock)
        if not math.isfinite(remaining):
            raise ValueError("remaining time must be finite")
        return max(0.0, remaining)

    def has(self, minimum_seconds: float) -> bool:
        if not math.isfinite(minimum_seconds) or minimum_seconds < 0:
            raise ValueError("minimum_seconds must be finite and non-negative")
        return self.remaining() >= minimum_seconds


def _read_clock(clock: Callable[[], float]) -> float:
    value = clock()
    if not math.isfinite(value):
        raise ValueError("clock reading must be finite")
    return value
