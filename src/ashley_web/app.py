"""Starlette application: the home page, the free-consultation API and the session shop."""

import json
import logging
import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from ashley_web import content
from ashley_web.booking import (
    MAX_MONTHS_AHEAD,
    BookingStore,
    SlotTakenError,
    month_availability,
    months_ahead,
    parse_booking,
)
from ashley_web.ebook import EbookRequestStore
from ashley_web.orders import MAX_QUANTITY, Order, OrderStore, format_euros, parse_order
from ashley_web.payments import MollieGateway, PaymentError, PaymentGateway
from ashley_web.validation import FormError, email_address

PACKAGE_DIR = Path(__file__).parent
DEFAULT_DB = Path("data/bookings.sqlite3")

# How many times the status page reloads itself while a payment is still being processed.
STATUS_RETRIES = 6

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
templates.env.filters["euros"] = format_euros


def asset_version(path: str) -> int:
    """Changes whenever the static file does, so browsers never reuse a stale cached copy."""
    return (PACKAGE_DIR / "static" / path).stat().st_mtime_ns


def gateway_from_env() -> PaymentGateway | None:
    """The live payment gateway, or None while no Mollie API key is configured."""
    key = os.environ.get("MOLLIE_API_KEY", "").strip()
    return MollieGateway(key) if key else None


def create_app(
    store: BookingStore | None = None,
    today: Callable[[], date] = date.today,
    orders: OrderStore | None = None,
    gateway: PaymentGateway | None = None,
    public_url: str | None = None,
    ebook_requests: EbookRequestStore | None = None,
) -> Starlette:
    """Build the app.

    `public_url` is the address the site is reachable at from the internet (for example
    https://example.com). The payment provider needs it to report payments back; without it
    the status page still checks each payment itself when the visitor returns.
    """
    db_path = Path(os.environ.get("ASHLEY_WEB_DB", DEFAULT_DB))
    bookings = store or BookingStore(db_path)
    orders = orders or OrderStore(db_path)
    ebook_requests = ebook_requests or EbookRequestStore(db_path)
    gateway = gateway or gateway_from_env()
    public_url = (public_url or os.environ.get("ASHLEY_WEB_PUBLIC_URL", "")).rstrip("/")

    def page(
        request: Request, template: str, context: dict[str, object], status_code: int = 200
    ) -> Response:
        shared = {"site": content.SITE, "year": today().year, "asset_version": asset_version}
        return templates.TemplateResponse(
            request, template, shared | context, status_code=status_code
        )

    def absolute_url(request: Request, name: str) -> str:
        if public_url:
            return public_url + request.app.url_path_for(name)
        return str(request.url_for(name))

    def home(request: Request) -> Response:
        return page(
            request,
            "index.html",
            {
                "slides": content.SLIDES,
                "pillars": content.PILLARS,
                "portfolio": content.PORTFOLIO,
                "offerings": content.OFFERINGS,
                "sessions": {session.slug: session for session in content.SESSIONS},
                "ebook": content.EBOOK,
            },
        )

    def availability(request: Request) -> Response:
        now = today()
        year, month = now.year, now.month
        if raw := request.query_params.get("month"):
            try:
                year, month = date.fromisoformat(f"{raw}-01").timetuple()[:2]
            except ValueError:
                return JSONResponse({"error": "month must look like YYYY-MM"}, status_code=400)
        offset = months_ahead(year, month, now)
        return JSONResponse(
            {
                "month": f"{year:04d}-{month:02d}",
                "prev": offset > 0,
                "next": offset < MAX_MONTHS_AHEAD,
                "days": month_availability(year, month, now, bookings.taken_in_month(year, month)),
            }
        )

    async def book(request: Request) -> Response:
        try:
            payload = json.loads(await request.body())
        except ValueError:
            return JSONResponse({"error": "Something went wrong. Please try again."}, 400)
        try:
            booking = parse_booking(payload, today())
        except FormError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        replaces = payload.get("replaces")
        try:
            token = bookings.book(booking, replaces if isinstance(replaces, str) else None)
        except SlotTakenError:
            return JSONResponse(
                {"error": "Sorry, that time has just been taken. Please choose another."},
                status_code=409,
            )
        return JSONResponse(
            {"token": token, "date": booking.day.isoformat(), "time": booking.time},
            status_code=201,
        )

    async def request_ebook(request: Request) -> Response:
        """Save the visitor's email; the reply says where to download the ebook, if anywhere."""
        try:
            payload = json.loads(await request.body())
        except ValueError:
            return JSONResponse({"error": "Something went wrong. Please try again."}, 400)
        try:
            email = email_address(payload if isinstance(payload, dict) else {})
        except FormError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        ebook_requests.add(email)
        file = content.EBOOK.file
        download = str(request.url_for("static", path=file)) if file else None
        return JSONResponse({"download": download}, status_code=201)

    def shop_page(
        request: Request,
        form: dict[str, str] | None = None,
        error: str | None = None,
        status_code: int = 200,
    ) -> Response:
        return page(
            request,
            "book.html",
            {
                "sessions": content.SESSIONS,
                "max_quantity": MAX_QUANTITY,
                "form": form or {},
                "error": error,
            },
            status_code,
        )

    def shop(request: Request) -> Response:
        return shop_page(request)

    async def checkout(request: Request) -> Response:
        """Save the order, start its payment and send the visitor to the hosted checkout."""
        body = (await request.body()).decode("utf-8", "replace")
        form = {key: values[-1] for key, values in parse_qs(body).items()}
        try:
            order_request = parse_order(form, content.SESSIONS)
        except FormError as exc:
            return shop_page(request, form, str(exc), 422)
        if gateway is None:
            unavailable = "Online payment is not available yet. Please get in touch to book."
            return shop_page(request, form, unavailable, 503)

        order = orders.create(order_request)
        redirect_url = f"{absolute_url(request, 'order_status')}?order={order.token}"
        try:
            payment = await run_in_threadpool(
                gateway.create,
                amount_cents=order.total_cents,
                description=f"{order.quantity} x {order.title} ({order.minutes} min), "
                f"order {order.number}",
                redirect_url=redirect_url,
                webhook_url=absolute_url(request, "payment_webhook") if public_url else None,
                metadata={"order": order.number, "name": order.name, "email": order.email},
            )
            if not payment.checkout_url:
                raise PaymentError("The payment has no checkout page.")
        except PaymentError:
            logger.exception("Could not start the payment for order %s", order.number)
            orders.set_status(order.token, "failed")
            failed = "We could not start the payment. Please try again in a moment."
            return shop_page(request, form, failed, 502)
        orders.attach_payment(order.token, payment.id)
        return RedirectResponse(payment.checkout_url, status_code=303)

    def sync_order(order: Order) -> Order:
        """Bring an unfinished order up to date with its payment. Raises PaymentError."""
        if order.is_final or not order.payment_id or gateway is None:
            return order
        status = gateway.fetch(order.payment_id).status
        if status != order.status:
            orders.set_status(order.token, status)
        return orders.by_token(order.token) or order

    def order_status(request: Request) -> Response:
        """Where the payment provider sends the visitor back to; never trusts the redirect."""
        order = orders.by_token(request.query_params.get("order", ""))
        if order is None:
            return page(request, "book_status.html", {"order": None}, 404)
        try:
            order = sync_order(order)
        except PaymentError:
            logger.exception("Could not check the payment for order %s", order.number)
        attempt = request.query_params.get("try", "")
        attempt = int(attempt) if attempt.isascii() and attempt.isdigit() else 0
        retry = None
        if not order.is_final and attempt < STATUS_RETRIES:
            retry = f"{request.url.path}?order={order.token}&try={attempt + 1}"
        return page(request, "book_status.html", {"order": order, "retry": retry})

    async def payment_webhook(request: Request) -> Response:
        """Mollie posts a payment id here when its status changes; we look the status up."""
        body = (await request.body()).decode("utf-8", "replace")
        payment_id = parse_qs(body).get("id", [""])[-1]
        order = orders.by_payment(payment_id)
        if order is not None:
            try:
                await run_in_threadpool(sync_order, order)
            except PaymentError:
                logger.exception("Could not check the payment for order %s", order.number)
                return Response(status_code=502)  # anything but 200 makes Mollie retry later
        # Unknown ids get the same answer, so the endpoint reveals nothing about our orders.
        return Response(status_code=200)

    return Starlette(
        routes=[
            Route("/", home),
            Route("/book", shop, name="shop"),
            Route("/book", checkout, methods=["POST"]),
            Route("/book/thanks", order_status, name="order_status"),
            Route("/api/availability", availability),
            Route("/api/bookings", book, methods=["POST"]),
            Route("/api/ebook", request_ebook, methods=["POST"]),
            Route(
                "/api/payments/webhook", payment_webhook, methods=["POST"], name="payment_webhook"
            ),
            Mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static"),
        ]
    )
