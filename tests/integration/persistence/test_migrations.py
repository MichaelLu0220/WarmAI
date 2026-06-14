from pathlib import Path

import aiosqlite
import pytest

from warmai.persistence.database import Database
from warmai.persistence.migrations import run_migrations


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "nested" / "test.db")

    await run_migrations(database, Path("migrations"))
    await run_migrations(database, Path("migrations"))

    async with database.connect() as connection:
        cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )

        assert await cursor.fetchall() == [(1,)]


@pytest.mark.asyncio
async def test_migrations_run_in_version_order(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "002_insert.sql").write_text(
        "INSERT INTO ordered_values(value) VALUES ('second');",
        encoding="utf-8",
    )
    (migration_directory / "001_create.sql").write_text(
        "CREATE TABLE ordered_values (value TEXT NOT NULL);",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        value_cursor = await connection.execute("SELECT value FROM ordered_values")

        assert await version_cursor.fetchall() == [(1,), (2,)]
        assert await value_cursor.fetchall() == [("second",)]


@pytest.mark.asyncio
async def test_failed_migration_is_rolled_back_and_not_recorded(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_broken.sql").write_text(
        "CREATE TABLE partial_table (value TEXT); THIS IS NOT VALID SQL;",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    with pytest.raises(aiosqlite.OperationalError):
        await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        table_cursor = await connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'partial_table'"
        )

        assert await version_cursor.fetchall() == []
        assert await table_cursor.fetchall() == []
