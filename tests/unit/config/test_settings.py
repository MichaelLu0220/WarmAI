from pathlib import Path

from warmai.config.settings import Settings


def test_settings_load_explicit_values(tmp_path: Path) -> None:
    settings = Settings(
        api_key="test-secret",
        database_path=tmp_path / "warmai.db",
        adapter_kind="mock",
    )

    assert settings.api_key.get_secret_value() == "test-secret"
    assert settings.database_path == tmp_path / "warmai.db"
    assert settings.internal_deadline_seconds == 4.5
    assert settings.pii_idempotency_ttl_seconds == 300
