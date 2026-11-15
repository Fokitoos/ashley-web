import io
import json
import urllib.error
import urllib.request
from email.message import Message

import pytest

from ashley_web.payments import MollieGateway, Payment, PaymentError


def answer(monkeypatch: pytest.MonkeyPatch, reply: object) -> list[urllib.request.Request]:
    """Make urlopen return `reply` as JSON (or raise it) and collect the requests sent."""
    sent: list[urllib.request.Request] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        sent.append(request)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return sent


def create(gateway: MollieGateway, webhook_url: str | None = None) -> Payment:
    return gateway.create(
        amount_cents=8400,
        description="2 x Online reading (60 min), order 7",
        redirect_url="https://ash.example/book/thanks?order=abc",
        webhook_url=webhook_url,
        metadata={"order": 7},
    )


def test_create_sends_a_mollie_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = {
        "id": "tr_abc",
        "status": "open",
        "_links": {"checkout": {"href": "https://www.mollie.com/checkout/select-method/abc"}},
    }
    sent = answer(monkeypatch, reply)
    payment = create(MollieGateway("test_key"), "https://ash.example/api/payments/webhook")

    assert payment.id == "tr_abc"
    assert payment.status == "open"
    assert payment.checkout_url == "https://www.mollie.com/checkout/select-method/abc"

    request = sent[0]
    assert request.get_method() == "POST"
    assert request.full_url == "https://api.mollie.com/v2/payments"
    assert request.get_header("Authorization") == "Bearer test_key"
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {
        "amount": {"currency": "EUR", "value": "84.00"},
        "description": "2 x Online reading (60 min), order 7",
        "redirectUrl": "https://ash.example/book/thanks?order=abc",
        "webhookUrl": "https://ash.example/api/payments/webhook",
        "metadata": {"order": 7},
    }


def test_create_leaves_out_the_webhook_when_there_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = answer(monkeypatch, {"id": "tr_abc", "status": "open"})
    create(MollieGateway("test_key"))
    assert isinstance(sent[0].data, bytes)
    assert "webhookUrl" not in json.loads(sent[0].data)


def test_fetch_reads_the_status(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = answer(monkeypatch, {"id": "tr_abc", "status": "paid"})
    payment = MollieGateway("test_key").fetch("tr_abc")
    assert (payment.status, payment.checkout_url) == ("paid", None)
    assert sent[0].get_method() == "GET"
    assert sent[0].full_url == "https://api.mollie.com/v2/payments/tr_abc"


def test_mollie_errors_become_payment_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    body = io.BytesIO(json.dumps({"status": 422, "detail": "The amount is too low"}).encode())
    error = urllib.error.HTTPError("https://api.mollie.com", 422, "Unprocessable", Message(), body)
    answer(monkeypatch, error)
    with pytest.raises(PaymentError, match="422: The amount is too low"):
        create(MollieGateway("test_key"))


def test_an_unreachable_or_odd_mollie_becomes_a_payment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer(monkeypatch, urllib.error.URLError("no route"))
    with pytest.raises(PaymentError, match="Could not reach Mollie"):
        MollieGateway("test_key").fetch("tr_abc")

    answer(monkeypatch, {"unexpected": True})
    with pytest.raises(PaymentError, match="unexpected response"):
        MollieGateway("test_key").fetch("tr_abc")
