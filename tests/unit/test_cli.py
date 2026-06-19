import json

import httpx
import pytest

from warmai.cli import build_payload, main


def test_build_payload_uses_given_request_id() -> None:
    payload = build_payload(
        "整理房間",
        "123e4567-e89b-12d3-a456-426614174000",
    )

    assert payload == {
        "text": "整理房間",
        "client_request_id": "123e4567-e89b-12d3-a456-426614174000",
    }


def test_main_posts_to_task_analysis_api(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        captured.update(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return httpx.Response(200, json={"schema_version": "1.0", "ok": True})

    monkeypatch.setattr("sys.argv", ["warmai", "整理房間", "--api-key", "secret"])
    monkeypatch.setattr("warmai.cli.httpx.post", fake_post)
    monkeypatch.setattr("warmai.cli.uuid4", lambda: "request-id-1")

    with pytest.raises(SystemExit) as captured_exit:
        main()

    assert captured_exit.value.code == 0
    assert captured == {
        "url": "http://127.0.0.1:8000/v1/task-analysis",
        "headers": {
            "X-API-Key": "secret",
            "Idempotency-Key": "request-id-1",
        },
        "json": {
            "text": "整理房間",
            "client_request_id": "request-id-1",
        },
        "timeout": 5.0,
    }
    assert json.loads(capsys.readouterr().out) == {"schema_version": "1.0", "ok": True}


def test_main_uses_env_api_key_and_strips_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        captured["url"] = url
        captured["api_key"] = headers["X-API-Key"]
        return httpx.Response(200, json={})

    monkeypatch.setattr(
        "sys.argv",
        ["warmai", "Clean the room", "--base-url", "http://example.test/"],
    )
    monkeypatch.setenv("WARMAI_API_KEY", "env-secret")
    monkeypatch.setattr("warmai.cli.httpx.post", fake_post)
    monkeypatch.setattr("warmai.cli.uuid4", lambda: "request-id-2")

    with pytest.raises(SystemExit) as captured_exit:
        main()

    assert captured_exit.value.code == 0
    assert captured == {
        "url": "http://example.test/v1/task-analysis",
        "api_key": "env-secret",
    }


def test_main_exits_nonzero_for_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "INVALID_INPUT"}})

    monkeypatch.setattr("sys.argv", ["warmai", "x", "--api-key", "secret"])
    monkeypatch.setattr("warmai.cli.httpx.post", fake_post)
    monkeypatch.setattr("warmai.cli.uuid4", lambda: "request-id-3")

    with pytest.raises(SystemExit) as captured_exit:
        main()

    assert captured_exit.value.code == 1


def test_main_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["warmai", "Clean the room"])
    monkeypatch.delenv("WARMAI_API_KEY", raising=False)

    with pytest.raises(SystemExit) as captured_exit:
        main()

    assert captured_exit.value.code == 2
