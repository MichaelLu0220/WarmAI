from dataclasses import fields
from pathlib import Path

import pytest

from warmai.persistence.database import Database
from warmai.persistence.events import InferenceEvent, InferenceEventRepository
from warmai.persistence.migrations import run_migrations


@pytest.mark.asyncio
async def test_event_repository_stores_and_retrieves_only_masked_fields(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    repository = InferenceEventRepository(database)
    event = InferenceEvent(
        request_id="123e4567-e89b-12d3-a456-426614174000",
        client_request_id="123e4567-e89b-12d3-a456-426614174001",
        raw_text_masked="Email [EMAIL_001]",
        raw_model_output_masked='{"reason":"Email [EMAIL_001]"}',
        response_json_masked='{"status":"ok","email":"[EMAIL_001]"}',
        input_hash="abc",
        pii_detected=True,
        training_eligible=False,
        model_version="mock-001",
        prompt_version="task-analysis-001",
        schema_version="1.0",
        latency_ms=10,
        validation_result="valid",
        fallback_stage="partial",
        recovered_fields=["score", "reason"],
        defaulted_fields=["warnings"],
    )

    await repository.insert(event)

    stored = await repository.get(event.request_id)

    assert stored == event
    assert stored is not None
    assert stored.pii_detected is True
    assert stored.training_eligible is False
    assert stored.recovered_fields == ["score", "reason"]
    assert stored.defaulted_fields == ["warnings"]

    async with database.connect() as connection:
        schema_cursor = await connection.execute("PRAGMA table_info(inference_events)")
        cursor = await connection.execute(
            """
            SELECT raw_text_masked, raw_model_output_masked, response_json_masked
            FROM inference_events
            WHERE request_id = ?
            """,
            (event.request_id,),
        )
        inference_event_columns = {row[1] for row in await schema_cursor.fetchall()}
        persisted_masked_fields = await cursor.fetchone()

    masked_payload_columns = {
        "raw_text_masked",
        "raw_model_output_masked",
        "response_json_masked",
    }
    repository_event_fields = {field.name for field in fields(InferenceEvent)}
    schema_payload_columns = {
        name
        for name in inference_event_columns
        if name.startswith(("raw_text", "raw_model_output", "response_json"))
    }
    repository_payload_fields = {
        name
        for name in repository_event_fields
        if name.startswith(("raw_text", "raw_model_output", "response_json"))
    }

    assert schema_payload_columns == masked_payload_columns
    assert repository_payload_fields == masked_payload_columns
    assert persisted_masked_fields == (
        event.raw_text_masked,
        event.raw_model_output_masked,
        event.response_json_masked,
    )
    assert "user@example.com" not in " ".join(persisted_masked_fields)
