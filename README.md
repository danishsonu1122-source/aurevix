# AUREVIX — Full-stack starter

A role-based cafe management web application starter using Flask + SQLite.

## Run locally
1. Install Python 3.10+
2. Open a terminal in this folder.
3. Create a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Start: `python app.py`
6. Open `http://127.0.0.1:5000`

## Demo accounts
All demo accounts use password `demo1234`:
- customer@demo.com
- owner@demo.com
- chef@demo.com
- waiter@demo.com
- admin@demo.com

## Included
- Server-side login sessions and password hashing
- Role-protected customer, owner, chef, waiter and super-admin workspaces
- SQLite database (created automatically)
- Menu listing and owner menu item creation
- Customer order placement
- Chef order acceptance / preparation / ready actions
- Waiter serve action
- Owner order overview and staff account creation
- Basic reward coin balance and redemption
- Admin cafe account overview
- Mustard, beige and warm ivory responsive UI

## Production work still required
This is a runnable full-stack starter, not a deployed production service. Before taking real restaurant/customer data:
- Set a strong `SECRET_KEY` environment variable.
- Use PostgreSQL or managed database for production.
- Add CSRF protection, rate limiting, email verification, password reset, audit logs and stronger operational security.
- Add tenant isolation and cafe-specific data ownership throughout every query.
- Integrate a real QR generator and public table-token URLs.
- Integrate a payment provider and subscription webhook handling.
- Add WebSocket/SSE notifications for cross-device real-time updates.
- Add backups, monitoring, HTTPS and deployment configuration.
- Have the security and payment flows reviewed before launch.

Demo accounts/data are seeded on first run. Do not use demo credentials in production.
