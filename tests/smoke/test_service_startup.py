from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from warmai.api.app import create_app
from warmai.config.settings import Settings
from warmai.inference.adapters.base import AdapterAvailabilityError, AdapterResponse
from warmai.inference.adapters.mock import MockAdapter
from warmai.inference.circuit_breaker import CircuitState


def _settings(tmp_path: Path, database_name: str) -> Settings:
    return Settings(
        api_key=SecretStr("secret"),
        database_path=tmp_path / database_name,
    )


def test_service_starts_migrates_and_accepts_request(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path, "smoke.db"),
        adapter=MockAdapter(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/task-analysis",
            headers={"X-API-Key": "secret", "Idempotency-Key": "smoke-1"},
            json={
                "text": "Clean the desk",
                "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

    assert response.status_code == 200
    assert (tmp_path / "smoke.db").exists()


class DownAdapter(MockAdapter):
    async def generate(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> AdapterResponse:
        self.calls += 1
        raise AdapterAvailabilityError("model unavailable")


def test_circuit_breaker_opens_and_returns_safe_default(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path, "breaker.db"),
        adapter=DownAdapter(),
    )

    with TestClient(app) as client:
        for index in range(3):
            request_id = f"123e4567-e89b-12d3-a456-42661417400{index}"
            response = client.post(
                "/v1/task-analysis",
                headers={
                    "X-API-Key": "secret",
                    "Idempotency-Key": f"breaker-{index}",
                },
                json={"text": "Clean the desk", "client_request_id": request_id},
            )
            assert response.status_code == 200
            assert response.json()["trace"]["fallback_stage"] == "safe_default"

    assert app.state.inference.breaker.state is CircuitState.OPEN
