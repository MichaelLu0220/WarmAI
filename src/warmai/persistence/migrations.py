import sqlite3
from pathlib import Path

from warmai.persistence.database import Database

_TRANSACTION_CONTROL = frozenset(
    {"BEGIN", "COMMIT", "END", "RELEASE", "ROLLBACK", "SAVEPOINT"}
)


def _migration_version(path: Path) -> int:
    version_text, separator, _ = path.stem.partition("_")
    if not separator or not version_text.isdigit():
        raise ValueError(f"Invalid migration filename: {path.name}")
    return int(version_text)


def _ordered_migrations(directory: Path) -> list[tuple[int, Path]]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Migration directory does not exist: {directory}")

    migrations = sorted(
        ((_migration_version(path), path) for path in directory.glob("*.sql")),
        key=lambda item: item[0],
    )
    versions = [version for version, _ in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("Migration versions must be unique")
    return migrations


def _first_sql_keyword(statement: str) -> str | None:
    index = 0
    while index < len(statement):
        if statement[index].isspace() or statement[index] == ";":
            index += 1
            continue
        if statement.startswith("--", index):
            newline = statement.find("\n", index + 2)
            if newline == -1:
                return None
            index = newline + 1
            continue
        if statement.startswith("/*", index):
            comment_end = statement.find("*/", index + 2)
            if comment_end == -1:
                return None
            index = comment_end + 2
            continue
        break

    keyword_start = index
    while index < len(statement) and (
        statement[index].isalpha() or statement[index] == "_"
    ):
        index += 1
    if keyword_start == index:
        return None
    return statement[keyword_start:index].upper()


def _sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []

    for character in script:
        buffer.append(character)
        if character != ";":
            continue
        candidate = "".join(buffer)
        if not sqlite3.complete_statement(candidate):
            continue
        if _first_sql_keyword(candidate) is not None:
            statements.append(candidate.strip())
        buffer.clear()

    remainder = "".join(buffer)
    if _first_sql_keyword(remainder) is None:
        return statements
    if not sqlite3.complete_statement(remainder + ";"):
        raise ValueError("Incomplete SQL statement in migration")
    statements.append(remainder.strip())
    return statements


def _migration_statements(path: Path) -> list[str]:
    statements = _sql_statements(path.read_text(encoding="utf-8"))
    for statement in statements:
        keyword = _first_sql_keyword(statement)
        if keyword in _TRANSACTION_CONTROL:
            raise ValueError(
                f"Migration {path.name} contains transaction control statement {keyword}"
            )
    return statements


async def run_migrations(database: Database, directory: Path) -> None:
    migrations = _ordered_migrations(directory)

    async with database.connect() as connection:
        try:
            await connection.execute("BEGIN IMMEDIATE")
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await connection.commit()
        except BaseException:
            await connection.rollback()
            raise

        for version, path in migrations:
            statements = _migration_statements(path)
            try:
                await connection.execute("BEGIN IMMEDIATE")
                async with connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?",
                    (version,),
                ) as cursor:
                    already_applied = await cursor.fetchone() is not None
                if already_applied:
                    await connection.commit()
                    continue

                for statement in statements:
                    await connection.execute(statement)
                await connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (version,),
                )
                await connection.commit()
            except BaseException:
                await connection.rollback()
                raise
