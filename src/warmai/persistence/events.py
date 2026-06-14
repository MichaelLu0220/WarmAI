import json
import sqlite3
from dataclasses import dataclass
from typing import cast

from warmai.persistence.database import Database


@dataclass(frozen=True)
class InferenceEvent:
    request_id: str
    client_request_id: str
    raw_text_masked: str
    raw_model_output_masked: str
    response_json_masked: str
    input_hash: str
    pii_detected: bool
    training_eligible: bool
    model_version: str
    prompt_version: str
    schema_version: str
    latency_ms: int
    validation_result: str
    fallback_stage: str
    recovered_fields: list[str]
    defaulted_fields: list[str]


def _decode_string_list(serialized: str) -> list[str]:
    value: object = json.loads(serialized)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("Expected a JSON list of strings")
    return cast(list[str], value)


class InferenceEventRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def insert(self, event: InferenceEvent) -> None:
        values = (
            event.request_id,
            event.client_request_id,
            event.raw_text_masked,
            event.raw_model_output_masked,
            event.response_json_masked,
            event.input_hash,
            int(event.pii_detected),
            int(event.training_eligible),
            event.model_version,
            event.prompt_version,
            event.schema_version,
            event.latency_ms,
            event.validation_result,
            event.fallback_stage,
            json.dumps(event.recovered_fields),
            json.dumps(event.defaulted_fields),
        )
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO inference_events (
                    request_id,
                    client_request_id,
                    raw_text_masked,
                    raw_model_output_masked,
                    response_json_masked,
                    input_hash,
                    pii_detected,
                    training_eligible,
                    model_version,
                    prompt_version,
                    schema_version,
                    latency_ms,
                    validation_result,
                    fallback_stage,
                    recovered_fields_json,
                    defaulted_fields_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            await connection.commit()

    async def get(self, request_id: str) -> InferenceEvent | None:
        async with self.database.connect() as connection:
            connection.row_factory = sqlite3.Row
            async with connection.execute(
                """
                SELECT
                    request_id,
                    client_request_id,
                    raw_text_masked,
                    raw_model_output_masked,
                    response_json_masked,
                    input_hash,
                    pii_detected,
                    training_eligible,
                    model_version,
                    prompt_version,
                    schema_version,
                    latency_ms,
                    validation_result,
                    fallback_stage,
                    recovered_fields_json,
                    defaulted_fields_json
                FROM inference_events
                WHERE request_id = ?
                """,
                (request_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return None
        return InferenceEvent(
            request_id=cast(str, row["request_id"]),
            client_request_id=cast(str, row["client_request_id"]),
            raw_text_masked=cast(str, row["raw_text_masked"]),
            raw_model_output_masked=cast(str, row["raw_model_output_masked"]),
            response_json_masked=cast(str, row["response_json_masked"]),
            input_hash=cast(str, row["input_hash"]),
            pii_detected=bool(row["pii_detected"]),
            training_eligible=bool(row["training_eligible"]),
            model_version=cast(str, row["model_version"]),
            prompt_version=cast(str, row["prompt_version"]),
            schema_version=cast(str, row["schema_version"]),
            latency_ms=cast(int, row["latency_ms"]),
            validation_result=cast(str, row["validation_result"]),
            fallback_stage=cast(str, row["fallback_stage"]),
            recovered_fields=_decode_string_list(cast(str, row["recovered_fields_json"])),
            defaulted_fields=_decode_string_list(cast(str, row["defaulted_fields_json"])),
        )
