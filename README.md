# ashley-web

Ash's personal portfolio and services webpage: a single server-rendered page (hero,
practice, about, portfolio, offerings) with a free-consultation booking calendar.

Built with Python 3.15, [Starlette](https://www.starlette.io/) and Jinja2; tooling is
uv, ruff and ty.

## Run

```sh
uv sync
uv run ashley-web                                              # http://127.0.0.1:8000
uv run uvicorn --factory ashley_web.app:create_app --reload    # with auto-reload
```

`HOST` and `PORT` change where it listens. Bookings are stored in SQLite at
`data/bookings.sqlite3` (override with `ASHLEY_WEB_DB`).

## Check

```sh
uv run ruff format . && uv run ruff check .
uv run ty check
uv run pytest
```

## Where things live

| Path | What |
| --- | --- |
| `src/ashley_web/content.py` | All copy and settings: name, contact details, accent colour, gradient, slides, offerings. Anything in `[SQUARE BRACKETS]` is a placeholder to fill in. |
| `src/ashley_web/booking.py` | Consultation hours (`WEEKDAY_SLOTS`, `SATURDAY_SLOTS`), validation, SQLite store. |
| `src/ashley_web/app.py` | Routes: `/`, `GET /api/availability`, `POST /api/bookings`. |
| `src/ashley_web/templates/` | `base.html`, `index.html`, one partial per section, shared macros. |
| `src/ashley_web/static/` | `css/site.css` (design tokens at the top) and `js/site.js` (carousel, booking picker). |

To use real photos or video, drop the files under `static/` and set `src` on the matching
`Slide` or `PortfolioItem` in `content.py`.
