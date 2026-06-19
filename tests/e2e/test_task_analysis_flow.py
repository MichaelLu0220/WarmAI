import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from warmai.api.app import create_app
from warmai.config.settings import Settings
from warmai.inference.adapters.mock import MockAdapter


def test_http_to_inference_to_masked_sqlite_to_response(tmp_path: Path) -> None:
    app = create_app(
        Settings(api_key=SecretStr("secret"), database_path=tmp_path / "test.db"),
        adapter=MockAdapter(),
    )
    payload = {
        "text": "提醒王小明整理房間",
        "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
    }
    headers = {"X-API-Key": "secret", "Idempotency-Key": "key-1"}

    with TestClient(app) as client:
        first = client.post("/v1/task-analysis", headers=headers, json=payload)
        replay = client.post("/v1/task-analysis", headers=headers, json=payload)

    assert first.status_code == 200
    assert first.json()["result"]["original_text"] == "提醒王小明整理房間"
    assert replay.json() == first.json()
    with sqlite3.connect(tmp_path / "test.db") as connection:
        stored = connection.execute(
            "SELECT raw_text_masked, response_json_masked FROM inference_events"
        ).fetchone()
    assert stored is not None
    assert "王小明" not in stored[0]
    assert "王小明" not in stored[1]
