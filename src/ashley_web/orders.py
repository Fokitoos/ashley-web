"""Paid sessions: order validation and storage."""

import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ashley_web.content import SessionType
from ashley_web.storage import SqliteStore
from ashley_web.validation import FormError, contact, text

MAX_QUANTITY = 10

# Order statuses mirror the payment provider's. Only PAID means money was received.
OPEN, PAID = "open", "paid"
FINAL_STATUSES = frozenset({PAID, "canceled", "expired", "failed"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    session TEXT NOT NULL,
    title TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_cents INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    payment_id TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at TEXT
)
"""
_COLUMNS = "id, token, title, minutes, quantity, unit_cents, name, email, status, payment_id"


def format_euros(cents: int) -> str:
    """4200 -> "€42", 4250 -> "€42.50"."""
    euros, rest = divmod(cents, 100)
    return f"€{euros}.{rest:02d}" if rest else f"€{euros}"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    session: SessionType
    quantity: int
    name: str
    email: str


@dataclass(frozen=True, slots=True)
class Order:
    """A stored order. Title, length and price are copied in, so later edits to the session
    in content.py never change what a visitor already bought."""

    number: int
    token: str
    title: str
    minutes: int
    quantity: int
    unit_cents: int
    name: str
    email: str
    status: str
    payment_id: str | None

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_cents

    @property
    def is_paid(self) -> bool:
        return self.status == PAID

    @property
    def is_final(self) -> bool:
        return self.status in FINAL_STATUSES


def parse_order(payload: Mapping[str, object], sessions: Sequence[SessionType]) -> OrderRequest:
    """Validate a submitted order, raising FormError with a visitor-facing message."""
    slug = text(payload, "session")
    session = next((s for s in sessions if s.slug == slug), None)
    if session is None:
        raise FormError("Please choose a session.")
    raw_quantity = text(payload, "quantity")
    quantity = int(raw_quantity) if raw_quantity.isascii() and raw_quantity.isdigit() else 0
    if not 1 <= quantity <= MAX_QUANTITY:
        raise FormError(f"Please choose between 1 and {MAX_QUANTITY} sessions.")
    name, email = contact(payload)
    return OrderRequest(session=session, quantity=quantity, name=name, email=email)


class OrderStore(SqliteStore):
    """SQLite-backed orders for paid sessions."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, _SCHEMA)

    def create(self, request: OrderRequest) -> Order:
        """Save a new, unpaid order. Its token is the visitor's key to the status page."""
        token = secrets.token_urlsafe(16)
        session = request.session
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO orders (token, session, title, minutes, quantity, unit_cents, "
                "name, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    token,
                    session.slug,
                    session.title,
                    session.minutes,
                    request.quantity,
                    session.price_cents,
                    request.name,
                    request.email,
                ),
            )
        order = self.by_token(token)
        assert order is not None
        return order

    def by_token(self, token: str) -> Order | None:
        return self._find("token", token)

    def by_payment(self, payment_id: str) -> Order | None:
        return self._find("payment_id", payment_id)

    def attach_payment(self, token: str, payment_id: str) -> None:
        with self._transaction() as conn:
            conn.execute("UPDATE orders SET payment_id = ? WHERE token = ?", (payment_id, token))

    def set_status(self, token: str, status: str) -> None:
        """Record the provider's latest status. A paid order stays paid."""
        with self._transaction() as conn:
            conn.execute(
                "UPDATE orders SET status = ?, "
                "paid_at = CASE WHEN ? = 'paid' THEN CURRENT_TIMESTAMP ELSE paid_at END "
                "WHERE token = ? AND status != 'paid'",
                (status, status, token),
            )

    def _find(self, column: str, value: str) -> Order | None:
        with self._transaction() as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM orders WHERE {column} = ?", (value,)
            ).fetchone()
        return Order(*row) if row else None
