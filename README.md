# CampusBite

CampusBite is an academic campus restaurant ordering and delivery application. It supports customer ordering, restaurant-owner operations, delivery-partner workflows, reviews and refunds, reminders, and optional AI explanations of customer order history.

This README describes the implementation in this repository. It does not imply production readiness or public deployment.

## 1. Project overview and V1 scope

CampusBite has three account roles: CUSTOMER, OWNER, and DELIVERY_PARTNER. Customers can browse without signing in; checkout and customer account features require authentication. Each owner is associated with one restaurant, and each order contains items from one restaurant.

Payments are simulated in an application ledger. There is no payment gateway, GPS/live map, RAG, embeddings, or vector database. AI explanations are optional; verified order facts are calculated by the backend and remain available when AI generation is unavailable.

## 2. Implemented features by role

### Customer

- Register as a CUSTOMER and log in. Owner and delivery-partner accounts are seeded, not publicly registered.
- Browse restaurants and available menu items as a guest. Search dishes by name and filter by minimum/maximum price.
- Use a guest-accessible cart persisted in localStorage. The cart enforces one restaurant at a time, asks before replacing a cart from another restaurant, and revalidates restored items against the current menu. Availability and price changes are shown; displayed prices are not silently accepted as current.
- Check out with one delivery address. The backend rechecks item availability and current prices, calculates the total from database prices, saves order-item price/name snapshots, and records a mock payment atomically. A changed price requires the customer to review and retry.
- View paginated order history, filter by status and order placement date range, open order details, and cancel an order only while it is PLACED. Cancellation marks the mock payment VOIDED and adds a separate ledger entry; it is not a refund.
- Submit one restaurant/order review after delivery. A delivered order remains review-eligible if it is later refunded.
- Request one full refund for an eligible delivered order. The owner reviews the request; approval records a separate refund ledger entry and changes order/payment status to REFUNDED.
- Ask stateless questions about their own order history at the order-insights page. Backend-calculated facts are displayed separately from optional AI commentary, including weekly payment activity and the complete list of active undelivered orders.

### Restaurant owner

- View and update the one restaurant associated with the authenticated owner.
- View, create, and edit menu items, including availability. Menu items are not hard-deleted in this interface.
- View paginated restaurant orders with status and order-placement date filters. Accept PLACED orders, advance preparation through PREPARING to READY, and assign an active delivery partner to a READY order.
- View order reminders for their restaurant. The scheduler checks every 60 seconds for PLACED or ACCEPTED orders whose last update is more than 15 minutes old. It records at most one reminder per order.
- Review refund requests for their restaurant and approve or reject pending requests. Approval is full-refund only.
- View dashboard metrics derived across the paginated order list:
  - **Pending:** PLACED, ACCEPTED, PREPARING, READY, ASSIGNED, or OUT_FOR_DELIVERY.
  - **Completed:** DELIVERED orders, including orders later refunded after delivery.
  - **Cancelled:** CANCELLED orders.
  - **Refunded:** REFUNDED orders, shown separately.
  - **Sales:** DELIVERED orders excluding REFUNDED orders.

### Delivery partner

- View and filter only orders assigned to the authenticated delivery partner.
- Open assigned delivery details and advance status from ASSIGNED to OUT_FOR_DELIVERY to DELIVERED.
- View delivery history. Orders in DELIVERED status appear in Delivered history. A subsequently refunded order with a delivered timestamp appears separately under **Delivered · Refunded**, retaining its REFUNDED status badge and without active delivery actions.
- The existing Delivered history filter requests DELIVERED status only and therefore excludes refunded orders. Refunded delivered orders are visible in the separate group when returned by the delivery API.

## 3. Technology stack and architecture

- **Frontend:** React, JavaScript, Vite, React Router
- **Backend:** Python 3.12, FastAPI, Pydantic, SQLAlchemy
- **Database:** PostgreSQL 17 for the Compose application
- **Migrations:** Alembic
- **Authentication:** bcrypt password hashing and JWT bearer access tokens
- **AI provider:** OpenAI API through the backend Python client
- **Local services:** Docker Compose

The frontend calls the FastAPI JSON API. Business rules, role/resource checks, price calculation, and financial facts are enforced or calculated on the backend. The frontend route guards support navigation and do not replace backend authorization.

## 4. Authentication, authorization, and data isolation

Public registration creates CUSTOMER accounts only. Each account has one role: CUSTOMER, OWNER, or DELIVERY_PARTNER. Owner and delivery-partner accounts are supplied by the explicit local demo seed.

Protected API requests validate the bearer token and load the active user and current role from the database. Endpoints scope customer orders to the authenticated customer, owner resources to the owner's restaurant, and delivery records to the assigned partner. Client-supplied role or owner/customer identifiers do not grant access.

JWT access-token expiry is configurable and is 60 minutes in the example configuration. The frontend stores only the access token in localStorage under `campusbite_access_token`, validates it through `GET /auth/me` on startup, and clears it on logout. Passwords and password hashes are not stored in browser storage or returned by authentication responses.

## 5. API overview

The interactive OpenAPI documentation is available at `/docs` while the backend is running.

| Area | Routes | Purpose |
|---|---|---|
| Health | `GET /health` | Basic liveness response; it does not check database connectivity. |
| Authentication | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | Customer registration, role login, current authenticated profile. |
| Restaurant discovery | `GET /restaurants`, `GET /restaurants/{restaurant_id}/menu-items` | Paginated restaurant list; available menu with search and price filters. |
| Owner restaurant/menu | `GET/PATCH /owner/restaurant`, `GET/POST /owner/menu-items`, `PATCH /owner/menu-items/{menu_item_id}` | View/update the owner's restaurant; list/create/edit menu items and availability. |
| Customer orders | `POST /orders`, `GET /orders`, `GET /orders/{order_id}`, `POST /orders/{order_id}/cancel` | Checkout, filtered history, customer-scoped detail, PLACED-only cancellation. |
| Reviews | `POST /orders/{order_id}/review`, `GET /orders/{order_id}/review` | Create/read the authenticated customer's order review. |
| Refund requests | `POST/GET /orders/{order_id}/refund-request`, `GET /owner/refund-requests`, `PATCH /owner/refund-requests/{request_id}` | Customer request/status and owner-scoped decision. |
| Owner orders | `GET /owner/orders`, `GET /owner/orders/delivery-partners`, `POST /owner/orders/{order_id}/accept`, `PATCH /owner/orders/{order_id}/status`, `POST /owner/orders/{order_id}/assign-delivery` | Owner-scoped order queue, active partner lookup, lifecycle actions and assignment. |
| Owner reminders | `GET /owner/reminders` | Paginated reminders for the authenticated owner's restaurant. |
| Delivery orders | `GET /delivery/orders`, `GET /delivery/orders/{order_id}`, `PATCH /delivery/orders/{order_id}/status` | Assigned delivery list/filter, scoped detail and permitted status update. |
| Order insights | `POST /insights/orders` | Customer-only question, verified facts and optional AI explanation. |

Paginated list endpoints use `page` and `page_size`, defaulting to 10 items per page (maximum 100 where configured). Customer order history accepts `status`, `placed_from`, and `placed_to`; owner order lists accept the corresponding status/date filters. Restaurant menu browsing accepts `search`, `min_price`, and `max_price`. The delivery-partner lookup at `GET /owner/orders/delivery-partners` returns a plain list rather than a paginated response.

Order lifecycle: PLACED → ACCEPTED → PREPARING → READY → ASSIGNED → OUT_FOR_DELIVERY → DELIVERED. Customers may cancel only from PLACED. Owner refund approval changes an eligible DELIVERED order to REFUNDED. These status changes are validated by the backend.

## 6. Database models, migrations, and seed data

Alembic migrations create these tables:

- `users`
- `restaurants`
- `menu_items`
- `orders`
- `order_items`
- `reviews`
- `payment_ledger`
- `refund_requests`
- `admin_reminder_logs` (used for owner order reminders)

Revision `0001_initial_schema` creates the relational schema and constraints, including one restaurant per owner, one review per order, and one refund request per order. Revision `0002_user_role_check` restricts user roles to CUSTOMER, OWNER, and DELIVERY_PARTNER. Order items preserve item name and unit-price snapshots. The payment ledger preserves the original payment and records separate VOIDED and REFUND entries.

The demo seed is explicit and is never run on application startup. From the backend directory, run `python -m app.seed_demo` (or use the Compose command below). It creates three fictional restaurants with five menu items each, three owner accounts, and two delivery-partner accounts. The seed validates existing records before committing; an exact rerun leaves them unchanged, while conflicting or edited seed records cause it to stop without committing.

## 7. Docker-backed backend setup

Requirements: Docker Desktop with Docker Compose, Git, Node.js/npm, and Python 3.12 if running backend tests locally.

From a fresh clone in Windows PowerShell:

1. Create the local environment file and edit it locally. Set a private random `JWT_SECRET_KEY` and keep the PostgreSQL values in `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `DATABASE_URL` consistent. Do not commit `.env`.

   ```powershell
   Copy-Item .env.example .env
   ```

2. Start PostgreSQL, build the backend image, migrate the database, seed demo data, then start the API:

   ```powershell
   docker compose up -d db
   docker compose build backend
   docker compose run --rm backend alembic upgrade head
   docker compose run --rm backend python -m app.seed_demo
   docker compose up -d backend
   ```

3. The API is at `http://localhost:8000`. Open `http://localhost:8000/docs` for API documentation. `http://localhost:8000/health` returns a basic liveness response only; it is not a database-connectivity check.

To stop the local Compose services:

```powershell
docker compose down
```

Do not add `-v` unless you intentionally want to delete the local PostgreSQL volume and its data. The Compose database is published on host port 5432.

## 8. Frontend local development

In a separate PowerShell terminal, from the repository root:

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev -- --host localhost --port 5173 --strictPort
```

Open `http://localhost:5173`. `VITE_API_BASE_URL` is the backend origin, for example `http://localhost:8000`, without an `/api` prefix. The frontend API client defaults to `http://localhost:8000` when the variable is unset.

## 9. Demo data and local-only credentials

Run the explicit seed command in the Docker setup above, or from `backend` after configuring the backend environment and migrating the database:

```powershell
python -m app.seed_demo
```

The seed creates the following local-only accounts. All use the development-only password `CampusBite-Local-Demo-2026!`.

| Role | Email |
|---|---|
| OWNER | `owner1@campusbite.local` |
| OWNER | `owner2@campusbite.local` |
| OWNER | `owner3@campusbite.local` |
| DELIVERY_PARTNER | `delivery1@campusbite.local` |
| DELIVERY_PARTNER | `delivery2@campusbite.local` |

Customers register through the public registration page. These fictional demo credentials are for local demonstration only and must not be reused outside it.

## 10. Environment-variable reference

The root `.env.example` is a template. Copy it to an ignored local `.env` and configure values there. Do not commit real secrets. The Compose backend receives the root `.env`; Vite variables are supplied to the frontend process.

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_DB` | Docker Compose | Local PostgreSQL database name. |
| `POSTGRES_USER` | Docker Compose | Local PostgreSQL user. |
| `POSTGRES_PASSWORD` | Docker Compose | Local PostgreSQL password. |
| `DATABASE_URL` | Backend/Alembic | SQLAlchemy connection URL. In Compose, the hostname must be the Compose database service (`db`); a host-run backend needs a host-reachable database address. |
| `JWT_SECRET_KEY` | Backend | JWT signing secret. Set a private random value locally; do not use a development fallback for real authentication. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | Access-token lifetime; the example uses 60 minutes. |
| `FRONTEND_ORIGIN` | Backend | Exact browser origin allowed by CORS; local example is `http://localhost:5173`. |
| `OPENAI_API_KEY` | Backend only | Evaluator-provided key for AI-generated commentary. Leave unset/blank to use verified facts without AI commentary. |
| `OPENAI_MODEL` | Backend only | Nonblank model name required by the current implementation for AI-generated commentary. |

Both `OPENAI_API_KEY` and a nonblank `OPENAI_MODEL` are required for generated explanations. Evaluators must configure their own key locally if they want AI commentary; never put a real key in frontend code, documentation, or source control. Missing configuration, rate limits, timeouts, provider failures, and unusable responses do not remove the separately returned backend-calculated facts. The frontend displays those facts and an availability notice without requiring an AI answer. AI provider calls are mocked in tests.

For the optional PostgreSQL integration tests, `TEST_DATABASE_URL` is read explicitly by the integration test setup, not from the application's `.env` fallback. See the test instructions below.

## 11. Backend tests and frontend build

### Backend test suite

From a fresh local Python 3.12 setup, in PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The standard backend tests use SQLite test fixtures and do not require the development PostgreSQL database. The opt-in PostgreSQL integration module is skipped unless `TEST_DATABASE_URL` is explicitly configured.

### Optional PostgreSQL integration tests

These tests are intended only for a separate disposable PostgreSQL instance on loopback port 55432, database `campusbite_stage2d`, user `campusbite_test`. Never point them at the regular development database on port 5432. The test fixture requires that database to already have Alembic revision `0002_user_role_check`; it does not migrate, create, drop, or reset tables. Apply migrations manually only after verifying that `DATABASE_URL` is explicitly set to the isolated test URL.

From `backend`, configure the test URL in the current PowerShell process without committing it:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://campusbite_test:<temporary-password>@127.0.0.1:55432/campusbite_stage2d"
```

Replace the placeholder with the disposable test database password. If that isolated database needs migrations, set `DATABASE_URL` to the same URL before running Alembic; verify both values carefully first:

```powershell
$env:DATABASE_URL = $env:TEST_DATABASE_URL
python -m alembic upgrade head
python -m pytest -q tests/test_postgres_integration.py
python -m pytest -q
```

The integration URL validator restricts the host, port, database, and username. Test identities include a per-run identifier to avoid collisions with existing test records. Do not use these commands against the regular development database.

### Frontend production build

There is no frontend automated test runner configured in `frontend/package.json`. To create the production bundle after `npm ci`:

```powershell
cd frontend
npm run build
```

## 12. Limitations and verification status

### Current limitations

- Payments are mock ledger entries; no real payment gateway is integrated.
- There is no GPS/live map, and delivery tracking is based on order status.
- AI explanations require evaluator-supplied backend configuration. The model is not permitted to calculate financial totals; backend facts are authoritative. Weekly activity covers Monday 00:00 Asia/Kolkata through the current time and uses ledger-entry posting timestamps. A refund or void reduces the week in which its ledger entry was posted, not the original order week.
- There is no RAG, embedding, vector database, or persistent AI chat history.
- Local Docker instructions are for development and demonstration, not production deployment or production-readiness certification.
- The Delivered history filter currently excludes REFUNDED orders; those with a delivery timestamp are presented separately under Delivered · Refunded.

### Recorded verification evidence

The browser checks below are previously recorded project evidence. The backend tests and frontend build were run against the current working tree for the AI insights correction.

- **15 November 2026:** A live browser journey was manually verified from customer checkout through owner acceptance/preparation, delivery assignment, delivery-partner status updates, and customer-visible DELIVERED status. Review submission and refund approval were also manually exercised.
- **Owner menu management:** create, edit, and availability changes were manually tested.
- **Backend verification (Python 3.12.10):** the non-PostgreSQL suite passed with 107 tests and 2 warnings; the separately run PostgreSQL integration suite passed with 18 tests and 2 warnings. Combined: 125 passed, 0 failed. The PostgreSQL integration tests ran separately against the isolated test database.
- **Frontend:** the production build passed after these changes. No frontend automated test suite is configured.
- **Not verified:** PostgreSQL reminder concurrency and real OpenAI generation. No public deployment is claimed.
