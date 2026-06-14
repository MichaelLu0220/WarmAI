import asyncio
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

_SQLITE_LOCK_ERRORS = {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
_WAL_RETRY_SECONDS = 30.0


async def _enable_wal(connection: aiosqlite.Connection) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _WAL_RETRY_SECONDS
    while True:
        try:
            await connection.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as error:
            error_code = getattr(error, "sqlite_errorcode", None)
            primary_error_code = error_code & 0xFF if isinstance(error_code, int) else None
            if (
                primary_error_code not in _SQLITE_LOCK_ERRORS
                or loop.time() >= deadline
            ):
                raise
            await asyncio.sleep(0.01)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.path, timeout=30.0)
        try:
            await connection.execute("PRAGMA busy_timeout = 30000")
            await _enable_wal(connection)
            await connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            await connection.close()
