import asyncio
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


@pytest.mark.parametrize(
    ("transaction_control", "script"),
    [
        (
            "COMMIT",
            "CREATE TABLE partial_table (value TEXT); "
            "INSERT INTO partial_table VALUES ('before commit'); COMMIT;",
        ),
        (
            "ROLLBACK",
            "CREATE TABLE partial_table (value TEXT); "
            "INSERT INTO partial_table VALUES ('before rollback'); ROLLBACK;",
        ),
        (
            "BEGIN",
            "CREATE TABLE partial_table (value TEXT); BEGIN; "
            "INSERT INTO partial_table VALUES ('after begin');",
        ),
        (
            "END",
            "CREATE TABLE partial_table (value TEXT); "
            "INSERT INTO partial_table VALUES ('before end'); END;",
        ),
        (
            "SAVEPOINT",
            "CREATE TABLE partial_table (value TEXT); SAVEPOINT nested; "
            "INSERT INTO partial_table VALUES ('inside savepoint'); RELEASE nested;",
        ),
        (
            "RELEASE",
            "CREATE TABLE partial_table (value TEXT); RELEASE missing_savepoint;",
        ),
    ],
)
@pytest.mark.asyncio
async def test_migration_rejects_transaction_control_without_partial_changes(
    tmp_path: Path,
    transaction_control: str,
    script: str,
) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_transaction_control.sql").write_text(
        script,
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    with pytest.raises(ValueError, match=transaction_control):
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


@pytest.mark.asyncio
async def test_transaction_words_in_comments_and_strings_are_allowed(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_allowed_words.sql").write_text(
        """
        -- BEGIN COMMIT ROLLBACK END SAVEPOINT RELEASE
        CREATE TABLE allowed_values (value TEXT NOT NULL);
        INSERT INTO allowed_values(value)
        VALUES ('BEGIN COMMIT ROLLBACK END SAVEPOINT RELEASE');
        /* COMMIT; ROLLBACK; BEGIN; END; SAVEPOINT ignored; RELEASE ignored; */
        """,
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        value_cursor = await connection.execute("SELECT value FROM allowed_values")

        assert await version_cursor.fetchall() == [(1,)]
        assert await value_cursor.fetchall() == [
            ("BEGIN COMMIT ROLLBACK END SAVEPOINT RELEASE",)
        ]


@pytest.mark.asyncio
async def test_concurrent_migration_runs_apply_each_version_once(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_create.sql").write_text(
        "CREATE TABLE concurrent_values (value TEXT NOT NULL);",
        encoding="utf-8",
    )
    (migration_directory / "002_insert.sql").write_text(
        "INSERT INTO concurrent_values(value) VALUES ('applied once');",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    await asyncio.gather(
        run_migrations(database, migration_directory),
        run_migrations(database, migration_directory),
    )

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        value_cursor = await connection.execute("SELECT value FROM concurrent_values")

        assert await version_cursor.fetchall() == [(1,), (2,)]
        assert await value_cursor.fetchall() == [("applied once",)]


@pytest.mark.asyncio
async def test_nonexistent_migration_directory_fails_before_database_creation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test.db"
    database = Database(database_path)

    with pytest.raises(FileNotFoundError):
        await run_migrations(database, tmp_path / "missing")

    assert not database_path.exists()
