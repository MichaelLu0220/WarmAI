from collections import deque
from typing import Any

from warmai.inference.adapters.base import AdapterResponse


class MockAdapter:
    def __init__(self, outputs: list[str] | None = None) -> None:
        self.outputs: deque[str] = deque(outputs or [])
        self.calls = 0

    async def generate(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> AdapterResponse:
        self.calls += 1
        raw = (
            self.outputs.popleft()
            if self.outputs
            else (
                '{"suggested_text":null,"score":3,'
                '"correction_confidence":0.9,"score_confidence":0.6,'
                '"warnings":[],"reason":"Mock analysis.",'
                '"is_task":true,"needs_review":false}'
            )
        )
        return AdapterResponse(raw_text=raw, model_version="mock-001")

    async def healthcheck(self) -> bool:
        return True
