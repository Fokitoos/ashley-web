"""Starlette application: one server-rendered page plus the booking API."""

import json
import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from ashley_web import content
from ashley_web.booking import (
    MAX_MONTHS_AHEAD,
    BookingError,
    BookingStore,
    SlotTakenError,
    month_availability,
    months_ahead,
    parse_booking,
)

PACKAGE_DIR = Path(__file__).parent
DEFAULT_DB = Path("data/bookings.sqlite3")

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


def create_app(
    store: BookingStore | None = None, today: Callable[[], date] = date.today
) -> Starlette:
    bookings = store or BookingStore(Path(os.environ.get("ASHLEY_WEB_DB", DEFAULT_DB)))

    def home(request: Request) -> Response:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "site": content.SITE,
                "slides": content.SLIDES,
                "pillars": content.PILLARS,
                "portfolio": content.PORTFOLIO,
                "offerings": content.OFFERINGS,
                "year": today().year,
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
        except BookingError as exc:
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

    return Starlette(
        routes=[
            Route("/", home),
            Route("/api/availability", availability),
            Route("/api/bookings", book, methods=["POST"]),
            Mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static"),
        ]
    )
