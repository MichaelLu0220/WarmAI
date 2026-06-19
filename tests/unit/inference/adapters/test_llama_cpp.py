import json

import httpx
import pytest

from warmai.config.model_config import (
    MAX_OUTPUT_TOKENS,
    PRESENCE_PENALTY,
    TEMPERATURE,
    TOP_K,
    TOP_P,
)
from warmai.inference.adapters.base import AdapterAvailabilityError
from warmai.inference.adapters.llama_cpp import LlamaCppAdapter


@pytest.mark.asyncio
async def test_adapter_requests_schema_constrained_non_thinking_json() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"score":3}'}}],
                "model": "warmai-base-001",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlamaCppAdapter(
        base_url="http://llama/",
        model="warmai-base-001",
        client=client,
    )

    response = await adapter.generate(
        prompt="prompt",
        json_schema={"type": "object"},
        timeout_seconds=1.0,
    )

    assert response.raw_text == '{"score":3}'
    assert response.model_version == "warmai-base-001"
    assert captured["model"] == "warmai-base-001"
    assert captured["messages"] == [{"role": "user", "content": "prompt"}]
    assert captured["stream"] is False
    assert captured["max_tokens"] == MAX_OUTPUT_TOKENS
    assert captured["temperature"] == TEMPERATURE
    assert captured["top_p"] == TOP_P
    assert captured["top_k"] == TOP_K
    assert captured["presence_penalty"] == PRESENCE_PENALTY
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["response_format"] == {
        "type": "json_schema",
        "schema": {"type": "object"},
    }
    await client.aclose()


@pytest.mark.asyncio
async def test_adapter_uses_configured_model_when_response_model_is_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlamaCppAdapter(
        base_url="http://llama",
        model="configured-model",
        client=client,
    )

    response = await adapter.generate(
        prompt="prompt",
        json_schema={"type": "object"},
        timeout_seconds=1.0,
    )

    assert response.model_version == "configured-model"
    await client.aclose()


@pytest.mark.asyncio
async def test_adapter_wraps_http_and_shape_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": 3}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlamaCppAdapter(
        base_url="http://llama",
        model="warmai-base-001",
        client=client,
    )

    with pytest.raises(AdapterAvailabilityError):
        await adapter.generate(
            prompt="prompt",
            json_schema={"type": "object"},
            timeout_seconds=1.0,
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_healthcheck_requires_loaded_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "warmai-base-001"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlamaCppAdapter(
        base_url="http://llama",
        model="warmai-base-001",
        client=client,
    )

    assert await adapter.healthcheck() is True
    await client.aclose()


@pytest.mark.asyncio
async def test_healthcheck_returns_false_for_unavailable_backend() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LlamaCppAdapter(
        base_url="http://llama",
        model="warmai-base-001",
        client=client,
    )

    assert await adapter.healthcheck() is False
    await client.aclose()
