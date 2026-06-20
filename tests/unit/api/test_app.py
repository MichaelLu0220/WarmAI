from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from warmai.api.app import build_adapter, create_app
from warmai.config.settings import Settings
from warmai.inference.adapters.llama_cpp import LlamaCppAdapter
from warmai.inference.adapters.mock import MockAdapter


def _settings(tmp_path: Path) -> Settings:
    return Settings(api_key=SecretStr("secret"), database_path=tmp_path / "test.db")


def test_build_adapter_selects_mock() -> None:
    settings = Settings(api_key=SecretStr("secret"), adapter_kind="mock")

    assert isinstance(build_adapter(settings), MockAdapter)


def test_build_adapter_selects_llama_cpp() -> None:
    settings = Settings(
        api_key=SecretStr("secret"),
        adapter_kind="llama_cpp",
        llama_cpp_base_url="http://llama/",
        llama_cpp_model="model-1",
    )

    adapter = build_adapter(settings)

    assert isinstance(adapter, LlamaCppAdapter)
    assert adapter.base_url == "http://llama"
    assert adapter.model == "model-1"


def test_task_analysis_allows_browser_preflight(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path), adapter=MockAdapter())

    with TestClient(app) as client:
        response = client.options(
            "/v1/task-analysis",
            headers={
                "Origin": "http://127.0.0.1:1420",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-api-key,idempotency-key,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()
