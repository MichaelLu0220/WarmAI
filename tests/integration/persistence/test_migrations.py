import asyncio
import sqlite3
from pathlib import Path

import aiosqlite
import pytest
from aiosqlite.context import Result

from warmai.persistence import database as database_module
from warmai.persistence.database import Database, _enable_wal
from warmai.persistence.migrations import run_migrations


def _synchronize_stale_version_reads(
    monkeypatch: pytest.MonkeyPatch,
    barrier: asyncio.Barrier,
) -> None:
    original_execute = aiosqlite.Connection.execute

    def synchronize_stale_read(
        connection: aiosqlite.Connection,
        sql: str,
        parameters: object = None,
    ) -> object:
        operation = original_execute(connection, sql, parameters)
        normalized_sql = " ".join(sql.split()).upper()
        if normalized_sql != "SELECT VERSION FROM SCHEMA_MIGRATIONS":
            return operation

        async def wait_for_both_stale_reads() -> aiosqlite.Cursor:
            await barrier.wait()
            return await operation

        return Result(wait_for_both_stale_reads())

    monkeypatch.setattr(aiosqlite.Connection, "execute", synchronize_stale_read)


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "nested" / "test.db")

    await run_migrations(database, Path("migrations"))
    await run_migrations(database, Path("migrations"))

    async with database.connect() as connection:
        cursor = await connection.execute("SELECT version FROM schema_migrations ORDER BY version")

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
        assert await value_cursor.fetchall() == [("BEGIN COMMIT ROLLBACK END SAVEPOINT RELEASE",)]


@pytest.mark.asyncio
async def test_bom_prefixed_migration_applies_normally(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_bom.sql").write_text(
        "\ufeffCREATE TABLE bom_values (value TEXT NOT NULL);"
        "INSERT INTO bom_values(value) VALUES ('applied');",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        value_cursor = await connection.execute("SELECT value FROM bom_values")

        assert await version_cursor.fetchall() == [(1,)]
        assert await value_cursor.fetchall() == [("applied",)]


@pytest.mark.asyncio
async def test_unknown_statement_prefix_rejects_whole_migration(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_invalid.sql").write_text(
        "@INVALID; CREATE TABLE should_not_exist (value TEXT);",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    with pytest.raises(ValueError, match="SQL keyword"):
        await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        table_cursor = await connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'should_not_exist'"
        )

        assert await version_cursor.fetchall() == []
        assert await table_cursor.fetchall() == []


@pytest.mark.asyncio
async def test_incomplete_sql_rejects_whole_migration(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_incomplete.sql").write_text(
        "CREATE TABLE should_not_exist (value TEXT); "
        "INSERT INTO should_not_exist(value) VALUES ('unterminated);",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    with pytest.raises(ValueError, match="Incomplete SQL statement"):
        await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        version_cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        table_cursor = await connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'should_not_exist'"
        )

        assert await version_cursor.fetchall() == []
        assert await table_cursor.fetchall() == []


@pytest.mark.asyncio
async def test_trigger_body_with_begin_and_end_is_preserved(tmp_path: Path) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_trigger.sql").write_text(
        """
        CREATE TABLE source_values (value TEXT NOT NULL);
        CREATE TABLE copied_values (value TEXT NOT NULL);
        CREATE TRIGGER copy_value
        AFTER INSERT ON source_values
        BEGIN
            INSERT INTO copied_values(value) VALUES (NEW.value);
        END;
        INSERT INTO source_values(value) VALUES ('copied');
        """,
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    await run_migrations(database, migration_directory)

    async with database.connect() as connection:
        cursor = await connection.execute("SELECT value FROM copied_values")

        assert await cursor.fetchall() == [("copied",)]


@pytest.mark.asyncio
async def test_concurrent_migration_runs_apply_each_version_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    stale_read_barrier = asyncio.Barrier(2)
    _synchronize_stale_version_reads(monkeypatch, stale_read_barrier)

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
async def test_stale_read_harness_exposes_prior_runner_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "001_create.sql").write_text(
        "CREATE TABLE concurrent_values (value TEXT NOT NULL);",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")
    stale_read_barrier = asyncio.Barrier(2)
    _synchronize_stale_version_reads(monkeypatch, stale_read_barrier)

    async def run_with_stale_read() -> None:
        async with database.connect() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY
                )
                """
            )
            await connection.commit()
            async with connection.execute("SELECT version FROM schema_migrations") as cursor:
                applied = {int(row[0]) for row in await cursor.fetchall()}

            if 1 in applied:
                return
            try:
                await connection.execute("BEGIN IMMEDIATE")
                await connection.execute(
                    (migration_directory / "001_create.sql").read_text(encoding="utf-8")
                )
                await connection.execute("INSERT INTO schema_migrations (version) VALUES (1)")
                await connection.commit()
            except BaseException:
                await connection.rollback()
                raise

    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        await asyncio.gather(run_with_stale_read(), run_with_stale_read())


@pytest.mark.asyncio
async def test_nonexistent_migration_directory_fails_before_database_creation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test.db"
    database = Database(database_path)

    with pytest.raises(FileNotFoundError):
        await run_migrations(database, tmp_path / "missing")

    assert not database_path.exists()


@pytest.mark.asyncio
async def test_enable_wal_retries_busy_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleep_delays: list[float] = []

    class BusyThenSuccessfulConnection:
        async def execute(self, sql: str) -> object:
            nonlocal calls
            calls += 1
            assert sql == "PRAGMA journal_mode = WAL"
            if calls == 1:
                error = sqlite3.OperationalError("database is locked")
                error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise error
            return object()

    async def record_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    await _enable_wal(BusyThenSuccessfulConnection())  # type: ignore[arg-type]

    assert calls == 2
    assert sleep_delays == [0.01]


@pytest.mark.asyncio
async def test_enable_wal_retries_extended_busy_code_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleep_delays: list[float] = []

    class BusyRecoveryThenSuccessfulConnection:
        async def execute(self, sql: str) -> object:
            nonlocal calls
            calls += 1
            assert sql == "PRAGMA journal_mode = WAL"
            if calls == 1:
                error = sqlite3.OperationalError("database is recovering")
                error.sqlite_errorcode = sqlite3.SQLITE_BUSY_RECOVERY
                raise error
            return object()

    async def record_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    await _enable_wal(
        BusyRecoveryThenSuccessfulConnection()  # type: ignore[arg-type]
    )

    assert calls == 2
    assert sleep_delays == [0.01]


@pytest.mark.asyncio
async def test_enable_wal_propagates_non_lock_error_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleep_delays: list[float] = []
    expected_error = sqlite3.OperationalError("not a database")
    expected_error.sqlite_errorcode = sqlite3.SQLITE_NOTADB

    class InvalidDatabaseConnection:
        async def execute(self, sql: str) -> object:
            nonlocal calls
            calls += 1
            assert sql == "PRAGMA journal_mode = WAL"
            raise expected_error

    async def record_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    with pytest.raises(sqlite3.OperationalError) as captured:
        await _enable_wal(InvalidDatabaseConnection())  # type: ignore[arg-type]

    assert captured.value is expected_error
    assert calls == 1
    assert sleep_delays == []


@pytest.mark.asyncio
async def test_enable_wal_stops_retrying_at_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleep_delays: list[float] = []
    expected_error = sqlite3.OperationalError("database is locked")
    expected_error.sqlite_errorcode = sqlite3.SQLITE_BUSY

    class AlwaysBusyConnection:
        async def execute(self, sql: str) -> object:
            nonlocal calls
            calls += 1
            assert sql == "PRAGMA journal_mode = WAL"
            raise expected_error

    async def record_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr(database_module, "_WAL_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(asyncio, "sleep", record_sleep)

    with pytest.raises(sqlite3.OperationalError) as captured:
        await _enable_wal(AlwaysBusyConnection())  # type: ignore[arg-type]

    assert captured.value is expected_error
    assert calls == 1
    assert sleep_delays == []
