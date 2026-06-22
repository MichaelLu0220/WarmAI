from typing import Any

import httpx

from warmai.config.model_config import (
    MAX_OUTPUT_TOKENS,
    PRESENCE_PENALTY,
    TEMPERATURE,
    TOP_K,
    TOP_P,
)
from warmai.inference.adapters.base import AdapterAvailabilityError, AdapterResponse


class LlamaCppAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        temperature: float | None = None,
        seed: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = TEMPERATURE if temperature is None else temperature
        self.seed = seed
        self.client = client or httpx.AsyncClient()

    async def generate(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> AdapterResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": self.temperature,
            "top_p": TOP_P,
            "top_k": TOP_K,
            "presence_penalty": PRESENCE_PENALTY,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "warmai_task_analysis",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            body: dict[str, Any] = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("llama.cpp response content must be a string")
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
            raise AdapterAvailabilityError(str(error)) from error

        model_version = body.get("model", self.model)
        if not isinstance(model_version, str):
            model_version = self.model
        return AdapterResponse(
            raw_text=content,
            model_version=model_version,
        )

    async def healthcheck(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/v1/models", timeout=2.0)
            return response.status_code == 200 and bool(response.json().get("data"))
        except (httpx.HTTPError, ValueError):
            return False
