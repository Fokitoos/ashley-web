from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from ashley_web import content
from ashley_web.app import create_app
from ashley_web.booking import BookingStore
from ashley_web.ebook import EbookRequestStore
from ashley_web.orders import MAX_QUANTITY, OrderStore, format_euros
from ashley_web.payments import Payment, PaymentError

CHECKOUT = "https://checkout.example/pay"
READING = content.SESSIONS[0]


@dataclass
class FakeGateway:
    """Stands in for Mollie: remembers what was asked and reports whatever status is set."""

    status: str = "open"
    fail: bool = False
    created: list[dict[str, object]] = field(default_factory=list)

    def create(
        self,
        *,
        amount_cents: int,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: Mapping[str, object],
    ) -> Payment:
        if self.fail:
            raise PaymentError("down")
        self.created.append(
            {
                "amount_cents": amount_cents,
                "description": description,
                "redirect_url": redirect_url,
                "webhook_url": webhook_url,
                "metadata": dict(metadata),
            }
        )
        return Payment(f"tr_{len(self.created)}", "open", CHECKOUT)

    def fetch(self, payment_id: str) -> Payment:
        if self.fail:
            raise PaymentError("down")
        return Payment(payment_id, self.status)


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def orders(tmp_path: Path) -> OrderStore:
    return OrderStore(tmp_path / "bookings.sqlite3")


def make_client(
    tmp_path: Path, orders: OrderStore, gateway: FakeGateway | None, public_url: str | None = None
) -> TestClient:
    app = create_app(
        store=BookingStore(tmp_path / "bookings.sqlite3"),
        orders=orders,
        gateway=gateway,
        public_url=public_url,
        ebook_requests=EbookRequestStore(tmp_path / "bookings.sqlite3"),
    )
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def client(tmp_path: Path, orders: OrderStore, gateway: FakeGateway) -> TestClient:
    return make_client(tmp_path, orders, gateway)


def order_form(**overrides: str) -> dict[str, str]:
    return {
        "session": READING.slug,
        "quantity": "2",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
    } | overrides


def buy(client: TestClient, gateway: FakeGateway, **overrides: str) -> str:
    """Place an order and return the status-page path the provider would send the visitor to."""
    response = client.post("/book", data=order_form(**overrides))
    assert response.status_code == 303
    assert response.headers["location"] == CHECKOUT
    url = urlsplit(str(gateway.created[-1]["redirect_url"]))
    return f"{url.path}?{url.query}"


def test_home_links_to_the_shop(client: TestClient) -> None:
    html = client.get("/").text
    assert 'href="http://testserver/book">Book now</a>' in html


def test_shop_page_shows_the_session(client: TestClient) -> None:
    response = client.get("/book")
    assert response.status_code == 200
    assert "Online reading" in response.text
    assert "60 minutes" in response.text
    assert "€42" in response.text


def test_format_euros() -> None:
    assert format_euros(4200) == "€42"
    assert format_euros(4250) == "€42.50"
    assert format_euros(5) == "€0.05"


def test_checkout_starts_a_payment_for_the_server_side_total(
    client: TestClient, gateway: FakeGateway, orders: OrderStore
) -> None:
    status_path = buy(client, gateway, quantity="3")

    payment = gateway.created[0]
    assert payment["amount_cents"] == 3 * READING.price_cents
    assert payment["description"] == "3 x Online reading (60 min), order 1"
    assert payment["webhook_url"] is None  # no public address configured
    assert payment["metadata"] == {"order": 1, "name": "Ada Lovelace", "email": "ada@example.com"}

    token = parse_qs(urlsplit(status_path).query)["order"][0]
    order = orders.by_token(token)
    assert order is not None
    assert (order.quantity, order.status, order.payment_id) == (3, "open", "tr_1")


def test_public_url_is_used_for_the_return_and_webhook_addresses(
    tmp_path: Path, orders: OrderStore, gateway: FakeGateway
) -> None:
    client = make_client(tmp_path, orders, gateway, public_url="https://ash.example/")
    client.post("/book", data=order_form())
    payment = gateway.created[0]
    assert str(payment["redirect_url"]).startswith("https://ash.example/book/thanks?order=")
    assert payment["webhook_url"] == "https://ash.example/api/payments/webhook"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"session": "nope"}, "Please choose a session."),
        ({"quantity": "0"}, f"Please choose between 1 and {MAX_QUANTITY} sessions."),
        ({"quantity": str(MAX_QUANTITY + 1)}, "Please choose between 1 and 10 sessions."),
        ({"quantity": "two"}, "Please choose between 1 and 10 sessions."),
        ({"quantity": "-1"}, "Please choose between 1 and 10 sessions."),
        ({"name": " "}, "Please add your name."),
        ({"email": "nope"}, "Please add a valid email address."),
    ],
)
def test_checkout_validation(
    client: TestClient, gateway: FakeGateway, overrides: dict[str, str], message: str
) -> None:
    response = client.post("/book", data=order_form(**overrides))
    assert response.status_code == 422
    assert message in response.text
    assert gateway.created == []


def test_checkout_keeps_what_the_visitor_typed(client: TestClient) -> None:
    html = client.post("/book", data=order_form(email="nope", quantity="4")).text
    assert 'value="Ada Lovelace"' in html
    assert 'value="4"' in html


def test_checkout_without_a_payment_provider(tmp_path: Path, orders: OrderStore) -> None:
    client = make_client(tmp_path, orders, gateway=None)
    response = client.post("/book", data=order_form())
    assert response.status_code == 503
    assert "Online payment is not available yet" in response.text


def test_checkout_when_the_provider_is_down(client: TestClient, gateway: FakeGateway) -> None:
    gateway.fail = True
    response = client.post("/book", data=order_form())
    assert response.status_code == 502
    assert "We could not start the payment" in response.text


def test_status_page_confirms_a_paid_order(client: TestClient, gateway: FakeGateway) -> None:
    status_path = buy(client, gateway)
    gateway.status = "paid"
    response = client.get(status_path)
    assert response.status_code == 200
    assert "Thank you, <em>Ada.</em>" in response.text
    assert "€84" in response.text
    assert "http-equiv" not in response.text


def test_status_page_waits_while_the_payment_is_open(
    client: TestClient, gateway: FakeGateway
) -> None:
    status_path = buy(client, gateway)
    html = client.get(status_path).text
    assert "being <em>processed.</em>" in html
    assert f'content="5; url={status_path}&amp;try=1"' in html

    # After the last automatic reload the page stops refreshing itself.
    html = client.get(f"{status_path}&try=6").text
    assert "http-equiv" not in html
    assert "Check again" in html


@pytest.mark.parametrize("status", ["canceled", "expired", "failed"])
def test_status_page_reports_an_unfinished_payment(
    client: TestClient, gateway: FakeGateway, status: str
) -> None:
    status_path = buy(client, gateway)
    gateway.status = status
    html = client.get(status_path).text
    assert "not <em>completed.</em>" in html
    assert "No money has been taken" in html


def test_status_page_still_loads_when_the_provider_is_down(
    client: TestClient, gateway: FakeGateway
) -> None:
    status_path = buy(client, gateway)
    gateway.fail = True
    assert "being <em>processed.</em>" in client.get(status_path).text


def test_status_page_for_an_unknown_order(client: TestClient) -> None:
    assert client.get("/book/thanks?order=nope").status_code == 404
    assert client.get("/book/thanks").status_code == 404


def test_webhook_marks_the_order_paid(
    client: TestClient, gateway: FakeGateway, orders: OrderStore
) -> None:
    buy(client, gateway)
    gateway.status = "paid"
    assert client.post("/api/payments/webhook", data={"id": "tr_1"}).status_code == 200
    order = orders.by_payment("tr_1")
    assert order is not None and order.is_paid

    # A paid order stays paid, whatever is reported afterwards.
    orders.set_status(order.token, "expired")
    again = orders.by_payment("tr_1")
    assert again is not None and again.is_paid


def test_webhook_answers_ok_for_unknown_payments(client: TestClient) -> None:
    assert client.post("/api/payments/webhook", data={"id": "tr_unknown"}).status_code == 200
    assert client.post("/api/payments/webhook", content=b"").status_code == 200


def test_webhook_asks_for_a_retry_when_the_provider_is_down(
    client: TestClient, gateway: FakeGateway
) -> None:
    buy(client, gateway)
    gateway.fail = True
    assert client.post("/api/payments/webhook", data={"id": "tr_1"}).status_code == 502
