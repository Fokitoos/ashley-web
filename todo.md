# Finishing the booking system

The code for buying sessions is on the `session-booking` branch. These are the steps left
for you; nothing here can be done from the code alone.

## 1. Set up Mollie

- [ ] Create an account at <https://www.mollie.com/> and complete its onboarding (business
      details, bank account for payouts, the website address). Mollie reviews the account
      before live payments are allowed, so start this early.
- [ ] In the Mollie dashboard, switch on the payment methods you want: iDEAL, cards, and
      any others (PayPal, Apple Pay, Bancontact, ...). The checkout shows whatever is
      switched on there; no code change is needed.
- [ ] Copy the **test** API key (`test_...`) from the dashboard's developer section.

## 2. Try it locally with the test key

- [ ] Run `MOLLIE_API_KEY=test_xxx uv run ashley-web` and open <http://127.0.0.1:8000/book>.
- [ ] Buy a session and choose "Paid" on Mollie's test screen: you should land on the
      "Thank you" page.
- [ ] Repeat and choose "Failed" / "Canceled" / "Expired": you should see "The payment was
      not completed" with a "Try again" button.
- [ ] Check the payment in the Mollie dashboard: the description should read like
      `2 x Online reading (60 min), order 1`, with name and email in the metadata.

## 3. Review the wording and details

All in `src/ashley_web/content.py` unless noted.

- [ ] `SESSIONS`: check the title, the 60 minutes, the €42 (`price_cents=4200`) and the
      short description of the online reading, which was written as a first draft.
- [ ] `OFFERINGS` → "Oracle readings": replace `[LENGTH]` and check the
      "€42 per online session" price line.
- [ ] `SITE`: fill in the real name, email, phone, city and time zone. The email is shown
      on the booking pages as the address to contact when something goes wrong.
- [ ] `templates/book.html` and `templates/book_status.html`: both say you will **email the
      client to arrange times** after payment. Change the wording if that is not how you
      want to work.

## 4. Decide how you hear about new orders

The site does not send any emails.

- [ ] Turn on payment notifications in Mollie (email or the Mollie app), or decide to
      check the dashboard regularly.
- [ ] Decide whether clients should get a confirmation email. If yes, that still has to
      be built (see "Later").

## 5. Legal and business information

Check these with your accountant or adviser; they are common requirements for selling
services online in the Netherlands and are usually looked at during Mollie's review.

- [ ] Business details on the site: trading name, KvK number, VAT number if you have one,
      and a contact address.
- [ ] Terms and conditions, including what happens when a client cancels or does not use
      a paid session, and how refunds work.
- [ ] Privacy statement: the site stores each buyer's name and email and passes them to
      Mollie to process the payment.
- [ ] Confirm whether the €42 should include VAT.

## 6. Go live

- [ ] Push the branch and merge it: `git push -u origin session-booking`, then open a pull
      request to `main`.
- [ ] Host the site on an address with HTTPS.
- [ ] Set these on the server:
  - `MOLLIE_API_KEY` = the **live** key (`live_...`). Keep it out of git.
  - `ASHLEY_WEB_PUBLIC_URL` = the site's address, e.g. `https://example.com`. With this
    set, an order is marked paid even if the client closes the tab before returning.
  - `ASHLEY_WEB_DB` = a path on storage that survives restarts and redeploys.
- [ ] Back up the SQLite file regularly; it holds the consultations and the orders.
- [ ] Make one real purchase yourself, confirm it shows as paid on the site and in Mollie,
      then refund it from the Mollie dashboard.

## Later (not built yet)

- [ ] Let clients pick the date and time of a paid session, instead of arranging by email.
- [ ] Confirmation emails to the client, and a notification email to you.
- [ ] A private page listing orders, so you do not depend on the Mollie dashboard.
- [ ] More session types: add a `SessionType` to `SESSIONS` and name its slug in the
      matching offering's `session=`.
