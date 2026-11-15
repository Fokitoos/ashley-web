"""Online payments through Mollie's hosted checkout.

Mollie shows the visitor every payment method enabled on the account (iDEAL, cards, PayPal,
Apple Pay, Bancontact, ...), so nothing here is specific to one method.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

MOLLIE_API = "https://api.mollie.com/v2"


class PaymentError(Exception):
    """The payment provider refused the request or could not be reached."""


@dataclass(frozen=True, slots=True)
class Payment:
    id: str
    status: str  # open, pending, authorized, paid, canceled, expired or failed
    checkout_url: str | None = None  # where to send the visitor to pay, while still open


class PaymentGateway(Protocol):
    def create(
        self,
        *,
        amount_cents: int,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: Mapping[str, object],
    ) -> Payment:
        """Start a payment and return it with the checkout URL to redirect the visitor to."""
        ...

    def fetch(self, payment_id: str) -> Payment:
        """Look up a payment's current status."""
        ...


class MollieGateway:
    """Mollie Payments API v2. A key starting with test_ runs in test mode, live_ for real."""

    def __init__(self, api_key: str, timeout: float = 15) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def create(
        self,
        *,
        amount_cents: int,
        description: str,
        redirect_url: str,
        webhook_url: str | None,
        metadata: Mapping[str, object],
    ) -> Payment:
        body: dict[str, object] = {
            "amount": {
                "currency": "EUR",
                "value": f"{amount_cents // 100}.{amount_cents % 100:02d}",
            },
            "description": description[:255],
            "redirectUrl": redirect_url,
            "metadata": dict(metadata),
        }
        # Mollie rejects webhook URLs it cannot reach (such as localhost), so it is optional.
        if webhook_url:
            body["webhookUrl"] = webhook_url
        return self._payment(self._request("POST", "/payments", body))

    def fetch(self, payment_id: str) -> Payment:
        return self._payment(self._request("GET", f"/payments/{quote(payment_id, safe='')}"))

    def _request(self, method: str, path: str, body: object = None) -> dict[str, object]:
        request = urllib.request.Request(
            MOLLIE_API + path,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ashley-web",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            raise PaymentError(f"Mollie answered {exc.code}: {_error_detail(exc)}") from exc
        except (OSError, ValueError) as exc:  # unreachable, timed out, or not JSON
            raise PaymentError(f"Could not reach Mollie: {exc}") from exc
        if not isinstance(data, dict):
            raise PaymentError("Mollie sent an unexpected response.")
        return data

    @staticmethod
    def _payment(data: Mapping[str, object]) -> Payment:
        payment_id, status = data.get("id"), data.get("status")
        if not isinstance(payment_id, str) or not isinstance(status, str):
            raise PaymentError("Mollie sent an unexpected response.")
        links = data.get("_links")
        checkout = links.get("checkout") if isinstance(links, dict) else None
        href = checkout.get("href") if isinstance(checkout, dict) else None
        return Payment(payment_id, status, href if isinstance(href, str) else None)


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        detail = json.load(exc).get("detail")
    except OSError, ValueError, AttributeError:
        detail = None
    return detail if isinstance(detail, str) else exc.reason
