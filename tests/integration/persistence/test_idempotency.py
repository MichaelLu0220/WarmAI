from pathlib import Path

import pytest

from warmai.persistence.database import Database
from warmai.persistence.idempotency import (
    IdempotencyConflict,
    IdempotencyInProgress,
    IdempotencyResultUnavailable,
    IdempotencyService,
)
from warmai.persistence.migrations import run_migrations


@pytest.mark.asyncio
async def test_non_pii_response_replays_from_sqlite(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    service = IdempotencyService(database, ttl_seconds=300)

    await service.reserve("key-1", "hash-1", "request-1")
    await service.complete("key-1", '{"status":"ok"}', pii_detected=False)

    assert await service.lookup("key-1", "hash-1") == '{"status":"ok"}'


@pytest.mark.asyncio
async def test_same_key_different_hash_conflicts(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    service = IdempotencyService(database, ttl_seconds=300)

    await service.reserve("key-1", "hash-1", "request-1")

    with pytest.raises(IdempotencyConflict):
        await service.lookup("key-1", "hash-2")


@pytest.mark.asyncio
async def test_same_key_same_hash_in_progress_is_rejected(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    service = IdempotencyService(database, ttl_seconds=300)

    await service.reserve("key-1", "hash-1", "request-1")

    with pytest.raises(IdempotencyInProgress):
        await service.lookup("key-1", "hash-1")
    with pytest.raises(IdempotencyInProgress):
        await service.reserve("key-1", "hash-1", "request-2")


@pytest.mark.asyncio
async def test_missing_key_lookup_returns_none(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    service = IdempotencyService(database, ttl_seconds=300)

    assert await service.lookup("missing-key", "hash-1") is None


@pytest.mark.asyncio
async def test_unexpired_pii_response_replays_from_memory_only(tmp_path: Path) -> None:
    now = [100.0]
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    service = IdempotencyService(database, ttl_seconds=5, clock=lambda: now[0])

    await service.reserve("key-1", "hash-1", "request-1")
    await service.complete("key-1", '{"status":"ok"}', pii_detected=True)

    assert await service.lookup("key-1", "hash-1") == '{"status":"ok"}'
    async with database.connect() as connection:
        cursor = await connection.execute(
            "SELECT response_json FROM idempotency_records WHERE idempotency_key = ?",
            ("key-1",),
        )
        assert await cursor.fetchone() == (None,)


@pytest.mark.asyncio
async def test_expired_pii_result_is_not_recomputed(tmp_path: Path) -> None:
    now = [100.0]
    database = Database(tmp_path / "test.db")
    await run_migrations(database, Path("migrations"))
    service = IdempotencyService(database, ttl_seconds=5, clock=lambda: now[0])

    await service.reserve("key-1", "hash-1", "request-1")
    await service.complete("key-1", '{"status":"ok"}', pii_detected=True)
    now[0] = 106.0

    with pytest.raises(IdempotencyResultUnavailable):
        await service.lookup("key-1", "hash-1")
