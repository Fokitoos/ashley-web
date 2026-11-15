"""Email addresses left in exchange for the free ebook."""

from pathlib import Path

from ashley_web.storage import SqliteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ebook_requests (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class EbookRequestStore(SqliteStore):
    """SQLite-backed list of everyone who asked for the ebook, one row per address."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, _SCHEMA)

    def add(self, email: str) -> None:
        """Remember the address; asking twice is fine and keeps the first request."""
        with self._transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO ebook_requests (email) VALUES (?)", (email,))

    def emails(self) -> list[str]:
        with self._transaction() as conn:
            rows = conn.execute("SELECT email FROM ebook_requests ORDER BY id")
            return [email for (email,) in rows]
