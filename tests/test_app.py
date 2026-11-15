from datetime import date
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ashley_web import content
from ashley_web.app import PACKAGE_DIR, create_app
from ashley_web.booking import (
    SATURDAY_SLOTS,
    WEEKDAY_SLOTS,
    BookingStore,
    month_availability,
    slots_for,
)

TODAY = date(2026, 11, 13)  # a Friday
MONDAY = "2026-11-16"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    store = BookingStore(tmp_path / "bookings.sqlite3")
    return TestClient(create_app(store=store, today=lambda: TODAY))


def booking(**overrides: object) -> dict[str, object]:
    return {
        "date": MONDAY,
        "time": "10:30",
        "name": "Sam Rivers",
        "email": "sam@example.com",
        "note": "",
    } | overrides


def test_slots_follow_the_weekly_pattern() -> None:
    assert slots_for(date(2026, 11, 16)) == WEEKDAY_SLOTS
    assert slots_for(date(2026, 11, 14)) == SATURDAY_SLOTS
    assert slots_for(date(2026, 11, 15)) == ()


def test_month_availability_skips_past_sundays_and_booked_slots() -> None:
    days = month_availability(
        2026, 11, TODAY, {MONDAY: {"09:00"}, "2026-11-14": set(SATURDAY_SLOTS)}
    )
    assert "2026-11-13" not in days  # today
    assert "2026-11-12" not in days  # past
    assert "2026-11-15" not in days  # Sunday
    assert "2026-11-14" not in days  # fully booked
    assert days[MONDAY] == list(WEEKDAY_SLOTS[1:])


def test_home_page_renders_every_section(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    for section in ("top", "practice", "about", "portfolio", "offerings", "book"):
        assert f'id="{section}"' in response.text
    assert "© 2026" in response.text


def test_static_assets_are_served(client: TestClient) -> None:
    assert client.get("/static/css/site.css").status_code == 200
    assert client.get("/static/js/site.js").status_code == 200


def test_media_paths_point_at_real_static_files(client: TestClient) -> None:
    sources = [m.src for m in (*content.SLIDES, *content.PORTFOLIO) if m.src]
    for src in sources:
        assert not src.startswith(("/", "static/", "src/")), (
            f"{src!r}: give the path relative to src/ashley_web/static/, e.g. 'media/photo.jpg'"
        )
        assert (PACKAGE_DIR / "static" / src).is_file(), f"{src!r} is not in src/ashley_web/static/"
        assert client.get(f"/static/{src}").status_code == 200


def test_availability_defaults_to_the_current_month(client: TestClient) -> None:
    data = client.get("/api/availability").json()
    assert data["month"] == "2026-11"
    assert data["prev"] is False
    assert data["next"] is True
    assert MONDAY in data["days"]


def test_availability_stops_at_the_booking_horizon(client: TestClient) -> None:
    assert client.get("/api/availability?month=2027-05").json()["next"] is False
    assert client.get("/api/availability?month=2027-06").json()["days"] == {}
    assert client.get("/api/availability?month=nope").status_code == 400


def test_booking_takes_the_slot(client: TestClient) -> None:
    response = client.post("/api/bookings", json=booking())
    assert response.status_code == 201
    assert response.json()["time"] == "10:30"
    assert "10:30" not in client.get("/api/availability").json()["days"][MONDAY]

    clash = client.post("/api/bookings", json=booking(email="other@example.com"))
    assert clash.status_code == 409


def test_rebooking_releases_the_earlier_slot(client: TestClient) -> None:
    token = client.post("/api/bookings", json=booking()).json()["token"]
    moved = client.post("/api/bookings", json=booking(time="13:00", replaces=token))
    assert moved.status_code == 201
    slots = client.get("/api/availability").json()["days"][MONDAY]
    assert "10:30" in slots
    assert "13:00" not in slots


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"date": None}, "Please choose a day and a time first."),
        ({"time": "03:00"}, "Please choose a day and a time first."),
        ({"date": "2026-11-15", "time": "09:00"}, "Please choose a day and a time first."),
        ({"date": "2026-11-13"}, "Please choose a day and a time first."),
        ({"name": "  "}, "Please add your name."),
        ({"email": "not-an-email"}, "Please add a valid email address."),
    ],
)
def test_booking_validation(client: TestClient, overrides: dict[str, object], message: str) -> None:
    response = client.post("/api/bookings", json=booking(**overrides))
    assert response.status_code == 422
    assert response.json() == {"error": message}


def test_booking_rejects_malformed_bodies(client: TestClient) -> None:
    assert client.post("/api/bookings", content=b"not json").status_code == 400
    assert client.post("/api/bookings", json=["a", "list"]).status_code == 422
