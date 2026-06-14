from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class AdapterAvailabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterResponse:
    raw_text: str
    model_version: str


@runtime_checkable
class InferenceAdapter(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> AdapterResponse: ...

    async def healthcheck(self) -> bool: ...
