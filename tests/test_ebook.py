from dataclasses import replace
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ashley_web import content
from ashley_web.app import create_app
from ashley_web.booking import BookingStore
from ashley_web.ebook import EbookRequestStore
from ashley_web.orders import OrderStore


@pytest.fixture
def requests(tmp_path: Path) -> EbookRequestStore:
    return EbookRequestStore(tmp_path / "bookings.sqlite3")


@pytest.fixture
def client(tmp_path: Path, requests: EbookRequestStore) -> TestClient:
    db = tmp_path / "bookings.sqlite3"
    app = create_app(store=BookingStore(db), orders=OrderStore(db), ebook_requests=requests)
    return TestClient(app)


def test_home_page_carries_the_offer(client: TestClient) -> None:
    html = client.get("/").text
    assert "data-ebook-offer" in html
    assert content.EBOOK.title in html


def test_other_pages_do_not_interrupt_with_the_offer(client: TestClient) -> None:
    assert "data-ebook-offer" not in client.get("/book").text


def test_request_saves_the_email(client: TestClient, requests: EbookRequestStore) -> None:
    response = client.post("/api/ebook", json={"email": " ada@example.com "})
    assert response.status_code == 201
    assert response.json() == {"download": None}  # no file configured: it is sent by hand
    assert requests.emails() == ["ada@example.com"]


def test_asking_twice_keeps_one_row(client: TestClient, requests: EbookRequestStore) -> None:
    assert client.post("/api/ebook", json={"email": "ada@example.com"}).status_code == 201
    assert client.post("/api/ebook", json={"email": "ADA@example.com"}).status_code == 201
    assert requests.emails() == ["ada@example.com"]


def test_request_offers_the_download_when_a_file_is_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(content, "EBOOK", replace(content.EBOOK, file="media/ebook.pdf"))
    response = client.post("/api/ebook", json={"email": "ada@example.com"})
    assert response.json() == {"download": "http://testserver/static/media/ebook.pdf"}


@pytest.mark.parametrize("payload", [{"email": "nope"}, {"email": ""}, {}, ["a", "list"]])
def test_request_validation(
    client: TestClient, requests: EbookRequestStore, payload: object
) -> None:
    response = client.post("/api/ebook", json=payload)
    assert response.status_code == 422
    assert response.json() == {"error": "Please add a valid email address."}
    assert requests.emails() == []


def test_request_rejects_malformed_bodies(client: TestClient) -> None:
    assert client.post("/api/ebook", content=b"not json").status_code == 400
