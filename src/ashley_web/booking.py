"""Free-consultation booking: availability rules, validation and storage."""

import calendar
import secrets
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ashley_web.storage import SqliteStore
from ashley_web.validation import FormError, contact, text

WEEKDAY_SLOTS = ("09:00", "10:30", "13:00", "16:30", "18:00", "19:30")
SATURDAY_SLOTS = ("09:30", "11:00", "12:30")
MAX_MONTHS_AHEAD = 6

_SATURDAY, _SUNDAY = 5, 6
_MAX_NOTE = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    time TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (day, time)
)
"""


class SlotTakenError(Exception):
    """Someone else booked the slot first."""


@dataclass(frozen=True, slots=True)
class BookingRequest:
    day: date
    time: str
    name: str
    email: str
    note: str = ""


def slots_for(day: date) -> tuple[str, ...]:
    """Consultation times offered on a given day, before bookings are taken out."""
    weekday = day.weekday()
    if weekday == _SUNDAY:
        return ()
    return SATURDAY_SLOTS if weekday == _SATURDAY else WEEKDAY_SLOTS


def months_ahead(year: int, month: int, today: date) -> int:
    return (year - today.year) * 12 + (month - today.month)


def is_bookable(day: date, today: date) -> bool:
    in_window = 0 <= months_ahead(day.year, day.month, today) <= MAX_MONTHS_AHEAD
    return day > today and in_window and bool(slots_for(day))


def month_availability(
    year: int, month: int, today: date, taken: Mapping[str, set[str]]
) -> dict[str, list[str]]:
    """Open times per ISO date for one month; days with nothing open are left out."""
    days: dict[str, list[str]] = {}
    for number in range(1, calendar.monthrange(year, month)[1] + 1):
        day = date(year, month, number)
        if not is_bookable(day, today):
            continue
        key = day.isoformat()
        booked = taken.get(key, set())
        if open_times := [t for t in slots_for(day) if t not in booked]:
            days[key] = open_times
    return days


def parse_booking(payload: object, today: date) -> BookingRequest:
    """Validate a submitted booking, raising FormError with a visitor-facing message."""
    if not isinstance(payload, dict):
        raise FormError("Please choose a day and a time first.")
    try:
        day = date.fromisoformat(text(payload, "date"))
    except ValueError:
        raise FormError("Please choose a day and a time first.") from None
    time = text(payload, "time")
    if not is_bookable(day, today) or time not in slots_for(day):
        raise FormError("Please choose a day and a time first.")

    name, email = contact(payload)
    note = text(payload, "note")
    if len(note) > _MAX_NOTE:
        raise FormError(f"Please keep your note under {_MAX_NOTE} characters.")
    return BookingRequest(day=day, time=time, name=name, email=email, note=note)


class BookingStore(SqliteStore):
    """SQLite-backed bookings; one consultation per (day, time)."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, _SCHEMA)

    def taken_in_month(self, year: int, month: int) -> dict[str, set[str]]:
        taken: dict[str, set[str]] = {}
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT day, time FROM bookings WHERE day LIKE ?", (f"{year:04d}-{month:02d}-%",)
            )
            for day, time in rows:
                taken.setdefault(day, set()).add(time)
        return taken

    def book(self, request: BookingRequest, replaces: str | None = None) -> str:
        """Save a booking and return its token.

        `replaces` is the token of the visitor's earlier booking, which is released in the
        same transaction so changing your mind never holds two slots.
        """
        token = secrets.token_urlsafe(16)
        try:
            with self._transaction() as conn:
                if replaces:
                    conn.execute("DELETE FROM bookings WHERE token = ?", (replaces,))
                conn.execute(
                    "INSERT INTO bookings (day, time, name, email, note, token) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request.day.isoformat(),
                        request.time,
                        request.name,
                        request.email,
                        request.note,
                        token,
                    ),
                )
        except sqlite3.IntegrityError:
            raise SlotTakenError from None
        return token
