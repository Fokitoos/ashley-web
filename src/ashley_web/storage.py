"""Shared SQLite plumbing for the site's small stores."""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path


class SqliteStore:
    """Opens a short-lived connection per transaction; `schema` is created on first use."""

    def __init__(self, path: Path, schema: str) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as conn:
            conn.execute(schema)

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection]:
        with closing(sqlite3.connect(self._path)) as conn, conn:
            yield conn
