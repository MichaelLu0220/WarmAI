import json
from typing import Any

import httpx
import pytest

from warmai.config.model_config import TEMPERATURE
from warmai.inference.adapters.llama_cpp import LlamaCppAdapter


def _client_capturing(captured: dict[str, Any]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"model": "m", "choices": [{"message": {"content": "{}"}}]},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_generate_uses_model_config_temperature_by_default() -> None:
    captured: dict[str, Any] = {}
    client = _client_capturing(captured)
    adapter = LlamaCppAdapter(base_url="http://llama", model="m", client=client)

    await adapter.generate(prompt="hi", json_schema={}, timeout_seconds=5.0)

    assert captured["temperature"] == TEMPERATURE
    assert "seed" not in captured
    await client.aclose()


@pytest.mark.asyncio
async def test_generate_applies_temperature_and_seed_overrides() -> None:
    captured: dict[str, Any] = {}
    client = _client_capturing(captured)
    adapter = LlamaCppAdapter(
        base_url="http://llama",
        model="m",
        temperature=0.0,
        seed=7,
        client=client,
    )

    await adapter.generate(prompt="hi", json_schema={}, timeout_seconds=5.0)

    assert captured["temperature"] == 0.0
    assert captured["seed"] == 7
    await client.aclose()
