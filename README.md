# ashley-web

Ash's personal portfolio and services webpage: a server-rendered home page (hero,
practice, about, portfolio, offerings) with a free-consultation booking calendar, plus a
`/book` page where visitors buy paid sessions online.

Built with Python 3.15, [Starlette](https://www.starlette.io/) and Jinja2; tooling is
uv, ruff and ty.

## Run

```sh
uv sync
uv run ashley-web                                              # http://127.0.0.1:8000
uv run uvicorn --factory ashley_web.app:create_app --reload    # with auto-reload
```

`HOST` and `PORT` change where it listens. Bookings and orders are stored in SQLite at
`data/bookings.sqlite3` (override with `ASHLEY_WEB_DB`).

## Paid sessions and payments

"Book now" leads to `/book`, where a visitor picks a number of sessions, leaves a name and
email, and pays on [Mollie](https://www.mollie.com/)'s hosted checkout. Mollie offers every
payment method switched on in its dashboard (iDEAL, cards, PayPal, Apple Pay, Bancontact,
...), so methods are added or removed there, not in this code.

| Variable | What |
| --- | --- |
| `MOLLIE_API_KEY` | API key from the Mollie dashboard. A `test_...` key takes pretend payments; a `live_...` key takes real money. Without a key, `/book` shows the form but says online payment is not available yet. |
| `ASHLEY_WEB_PUBLIC_URL` | The site's public address, e.g. `https://example.com`. Set it in production: Mollie then reports each payment to `/api/payments/webhook`, so an order is marked paid even if the visitor closes the tab before returning. Leave it unset locally (Mollie cannot reach `localhost`); the return page then checks the payment itself. |

```sh
MOLLIE_API_KEY=test_xxx uv run ashley-web      # try the whole flow with Mollie's test screen
```

Sessions for sale are listed in `SESSIONS` in `content.py` (title, length, price in euro
cents). An offering gets its "Book now" button by naming a session slug in `session=`.

Each order is saved in the `orders` table with its status (`open`, `paid`, `canceled`,
`expired`, `failed`). The site does not send emails: paid orders appear in the Mollie
dashboard, with the order number, name and email in the payment's description and metadata.

## Free ebook pop-up

The first time someone opens the home page, a pop-up offers a free ebook in exchange for
their email address. It appears once per visitor (remembered in the browser's
`localStorage` under `ebook-offer-seen`), and never on the `/book` pages. To see it again
while working on it, open the site in a private window.

Set the ebook up in `EBOOK` in `content.py`: its title, a short blurb, and optionally
`file` and `cover` (paths under `static/`). With `file` set, the visitor gets a download
button straight away; without it, the pop-up says the ebook is on its way by email, and
sending it is up to you. The site itself sends no email.

Addresses are saved in the `ebook_requests` table:

```sh
sqlite3 data/bookings.sqlite3 "SELECT email, created_at FROM ebook_requests"
```

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
| `src/ashley_web/orders.py` | Paid-session orders: validation, `MAX_QUANTITY`, SQLite store. |
| `src/ashley_web/ebook.py` | SQLite store for the email addresses left for the free ebook. |
| `src/ashley_web/payments.py` | The Mollie gateway (create a payment, look up its status). |
| `src/ashley_web/app.py` | Routes: `/`, `/book`, `/book/thanks`, `GET /api/availability`, `POST /api/bookings`, `POST /api/ebook`, `POST /api/payments/webhook`. |
| `src/ashley_web/templates/` | `base.html`, `index.html`, `book.html`, `book_status.html`, one partial per section, shared macros. |
| `src/ashley_web/static/` | `css/site.css` (design tokens at the top) and `js/site.js` (carousel, booking picker, session quantity, ebook pop-up). |
| `src/ashley_web/static/fonts/` | Jost and Cormorant Garamond, served from this site instead of Google Fonts so pages load nothing from third parties. Both are under the SIL Open Font License (`OFL-*.txt`). |

To use real photos or video, drop the files under `static/` and set `src` on the matching
`Slide` or `PortfolioItem` in `content.py`.
