from pathlib import Path

from warmai.persistence.database import Database


def _migration_version(path: Path) -> int:
    version_text, separator, _ = path.stem.partition("_")
    if not separator or not version_text.isdigit():
        raise ValueError(f"Invalid migration filename: {path.name}")
    return int(version_text)


def _ordered_migrations(directory: Path) -> list[tuple[int, Path]]:
    migrations = sorted(
        ((_migration_version(path), path) for path in directory.glob("*.sql")),
        key=lambda item: item[0],
    )
    versions = [version for version, _ in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("Migration versions must be unique")
    return migrations


async def run_migrations(database: Database, directory: Path) -> None:
    migrations = _ordered_migrations(directory)

    async with database.connect() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await connection.commit()

        async with connection.execute("SELECT version FROM schema_migrations") as cursor:
            applied = {int(row[0]) for row in await cursor.fetchall()}

        for version, path in migrations:
            if version in applied:
                continue

            script = path.read_text(encoding="utf-8").rstrip()
            transaction_script = (
                "BEGIN IMMEDIATE;\n"
                f"{script}\n"
                f"INSERT INTO schema_migrations (version) VALUES ({version});\n"
                "COMMIT;"
            )
            try:
                await connection.executescript(transaction_script)
            except BaseException:
                await connection.rollback()
                raise
            applied.add(version)
