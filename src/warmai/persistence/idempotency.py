import time
from collections.abc import Callable
from typing import cast

from warmai.persistence.database import Database


class IdempotencyConflict(RuntimeError):
    pass


class IdempotencyInProgress(RuntimeError):
    pass


class IdempotencyResultUnavailable(RuntimeError):
    pass


class IdempotencyService:
    def __init__(
        self,
        database: Database,
        ttl_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.database = database
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._pii_cache: dict[str, tuple[float, str]] = {}

    async def reserve(self, key: str, input_hash: str, request_id: str) -> None:
        async with self.database.connect() as connection:
            try:
                await connection.execute("BEGIN IMMEDIATE")
                cursor = await connection.execute(
                    """
                    SELECT input_hash, status
                    FROM idempotency_records
                    WHERE idempotency_key = ?
                    """,
                    (key,),
                )
                row = await cursor.fetchone()
                if row is not None:
                    await connection.rollback()
                    if row[0] != input_hash:
                        raise IdempotencyConflict
                    raise IdempotencyInProgress

                await connection.execute(
                    """
                    INSERT INTO idempotency_records (
                        idempotency_key,
                        input_hash,
                        request_id,
                        status
                    ) VALUES (?, ?, ?, 'in_progress')
                    """,
                    (key, input_hash, request_id),
                )
                await connection.commit()
            except BaseException:
                if connection.in_transaction:
                    await connection.rollback()
                raise

    async def complete(self, key: str, response_json: str, pii_detected: bool) -> None:
        persisted = None if pii_detected else response_json
        if pii_detected:
            self._pii_cache[key] = (self.clock() + self.ttl_seconds, response_json)

        async with self.database.connect() as connection:
            await connection.execute(
                """
                UPDATE idempotency_records
                SET status = 'completed',
                    pii_detected = ?,
                    response_json = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = ?
                """,
                (int(pii_detected), persisted, key),
            )
            await connection.commit()

    async def lookup(self, key: str, input_hash: str) -> str | None:
        async with self.database.connect() as connection:
            cursor = await connection.execute(
                """
                SELECT input_hash, status, pii_detected, response_json
                FROM idempotency_records
                WHERE idempotency_key = ?
                """,
                (key,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None
        if row[0] != input_hash:
            raise IdempotencyConflict
        if row[1] == "in_progress":
            raise IdempotencyInProgress
        if not row[2]:
            return cast(str, row[3])

        cached = self._pii_cache.get(key)
        if cached is not None and cached[0] >= self.clock():
            return cached[1]

        self._pii_cache.pop(key, None)
        raise IdempotencyResultUnavailable
