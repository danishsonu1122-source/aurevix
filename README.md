# AUREVIX — Cafe management MVP

A role-based cafe platform starter built with Flask + SQLite. It now includes a public table-specific QR menu, order creation and tracking, kitchen and waiter workflow, owner operations, loyalty rules/games, manual subscription requests and Super Admin review.

## Run locally (Windows)
1. Install Python 3.10 or newer.
2. Extract this ZIP and open a terminal inside `aurevix_fullstack`.
3. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install dependencies: `pip install -r requirements.txt`
5. Set a development secret (PowerShell): `$env:SECRET_KEY="replace-with-a-long-random-secret"`
6. Start: `python app.py`
7. Open `http://127.0.0.1:5000`.

macOS/Linux: use `python3 -m venv .venv`, `source .venv/bin/activate`, and `export SECRET_KEY="..."`.

## Demo accounts
All demo accounts use password `demo1234`:
- customer@demo.com
- owner@demo.com
- chef@demo.com
- waiter@demo.com
- admin@demo.com

Change demo passwords before any public deployment. The demo database is created automatically on first run in `aurevix.db`.

## Main flows
- **Cafe signup:** owner creates a cafe workspace, initial tables and QR tokens.
- **QR ordering:** owner opens `Tables & QR`, prints a table QR, and customer scans it to open the cafe-specific public menu.
- **Customer:** submits a table order and receives a private order-tracking page that refreshes automatically.
- **Chef:** New → Accepted → Preparing → Ready. Prep time is recorded.
- **Waiter:** Ready → Served; can record payment status.
- **Owner:** menu, staff accounts/permissions, tables/QR, order overview, loyalty rules, reports, cafe settings and subscription requests.
- **Rewards:** coins are earned on served orders within a daily cap. Promotional games have three attempts per customer/day. Coins are non-cash; redemption is confirmed at the counter.
- **Super Admin:** activate/suspend cafe accounts, manage plan assignment and manually review subscription payment references.

## Important scope and launch limitations
This is a functional **MVP starter**, not a fully audited, hosted commercial SaaS. Do not collect real customer/payment data or sell subscriptions from it until the following are implemented and reviewed:

1. **Security:** implement CSRF protection on every state-changing form, add login throttling, password reset/email verification, MFA for admins, audit logs, strict content security policy, secure proxy configuration, secrets management and security testing. This build uses password hashing, server sessions, role checks and cafe-scoped queries, but has not had a security audit.
2. **Database/tenancy:** migrate SQLite to managed PostgreSQL, add automated backups, migrations, tenant-isolation tests, data retention/export/deletion and disaster recovery.
3. **Payments:** payment requests are manual-review placeholders. Integrate a supported Pakistan payment provider (or card processor), signed webhooks, refunds, invoices, tax handling and reconciliation. Never store card details.
4. **Notifications:** dashboard queues and tracking refresh by polling; add authenticated WebSockets/SSE and push/email/WhatsApp/SMS providers for true instant notifications.
5. **Operations:** deploy behind HTTPS with a production WSGI server (e.g. Gunicorn), custom domain, monitoring, logs, uptime checks and error reporting. Configure `SECRET_KEY`, `DATABASE_PATH`, `PORT`, and `COOKIE_SECURE=1` in production.
6. **Product completion:** add image uploads, modifiers/add-ons, inventory, discounts/coupons, kitchen printers, receipt printing, multi-branch support, localized currencies/languages, advanced date-filtered exports, proper customer account login, real loyalty redemption validation at checkout, and accessible UI testing.
7. **Commercial details:** Starter/Growth/Pro prices shown are draft examples in PKR, not validated market pricing. Enterprise is custom. Confirm plan limits, legal terms, privacy policy, support and billing cycle before launch.

## Production server example
After setting environment variables and configuring a production database, run:
`gunicorn --workers 2 --bind 0.0.0.0:${PORT:-8000} app:app`

The first-run demo seed is intended for local testing only. Remove demo users and seed data before a public launch.
