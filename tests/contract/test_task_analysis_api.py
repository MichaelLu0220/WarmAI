from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from warmai.api.app import create_app
from warmai.config.settings import Settings
from warmai.inference.adapters.mock import MockAdapter


def _settings(tmp_path: Path) -> Settings:
    return Settings(api_key=SecretStr("secret"), database_path=tmp_path / "test.db")


def test_rejects_missing_api_key(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path),
        adapter=MockAdapter(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/task-analysis",
            headers={"Idempotency-Key": "key-1"},
            json={
                "text": "Clean the room",
                "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_rejects_unanalyzable_input_without_calling_model(tmp_path: Path) -> None:
    adapter = MockAdapter()
    app = create_app(
        _settings(tmp_path),
        adapter=adapter,
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/task-analysis",
            headers={"X-API-Key": "secret", "Idempotency-Key": "key-1"},
            json={
                "text": "👍👍👍",
                "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNANALYZABLE_INPUT"
    assert adapter.calls == 0


def test_rejects_over_200_characters_as_invalid_input(tmp_path: Path) -> None:
    adapter = MockAdapter()
    app = create_app(
        _settings(tmp_path),
        adapter=adapter,
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/task-analysis",
            headers={"X-API-Key": "secret", "Idempotency-Key": "key-2"},
            json={
                "text": "a" * 201,
                "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert adapter.calls == 0


def test_replays_identical_idempotency_request(tmp_path: Path) -> None:
    adapter = MockAdapter()
    app = create_app(
        _settings(tmp_path),
        adapter=adapter,
    )
    payload = {
        "text": "Clean the room",
        "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
    }
    headers = {"X-API-Key": "secret", "Idempotency-Key": "key-3"}

    with TestClient(app) as client:
        first = client.post("/v1/task-analysis", headers=headers, json=payload)
        replay = client.post("/v1/task-analysis", headers=headers, json=payload)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert adapter.calls == 1


def test_idempotency_key_conflict_returns_409(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path),
        adapter=MockAdapter(),
    )
    headers = {"X-API-Key": "secret", "Idempotency-Key": "key-4"}

    with TestClient(app) as client:
        first = client.post(
            "/v1/task-analysis",
            headers=headers,
            json={
                "text": "Clean the room",
                "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )
        conflict = client.post(
            "/v1/task-analysis",
            headers=headers,
            json={
                "text": "Clean the desk",
                "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
