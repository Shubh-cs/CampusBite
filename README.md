# CampusBite 🍔

CampusBite is an academic capstone project for restaurant ordering and delivery. This repository is being implemented in small, reviewable milestones against the supplied project problem statement.

## Technology

- Frontend: React, JavaScript, Vite, React Router
- Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy
- Database: PostgreSQL
- Database migrations: Alembic
- Authentication: bcrypt password hashing and JWT bearer access tokens
- Local backend/database: Docker Compose

## Milestone 1: Project foundation

The foundation includes the React app shell, FastAPI health endpoint, relational models, Alembic migrations, and local PostgreSQL/backend containers.

**Verification (13 November 2026):** Docker Compose configuration validated; backend image built; PostgreSQL and FastAPI containers started and reported healthy; revision `0001_initial_schema` applied; all nine application tables were present; `/health` and `/docs` returned HTTP 200.

## Milestone 2: Authentication and authorization

- Public registration creates CUSTOMER accounts only. The registration form has no role selector, and the API rejects a submitted role.
- Login accepts CUSTOMER, OWNER, and DELIVERY_PARTNER accounts. Owner and delivery-partner accounts must already exist in the database; public registration cannot create them.
- Passwords are hashed with bcrypt. Successful login returns a JWT access token with a configurable expiry (60 minutes by default).
- `GET /auth/me` validates the bearer token and returns the current user’s public profile.
- The reusable backend `require_roles(...)` dependency validates the token, loads the active user from PostgreSQL, and checks that user’s current database role. Role-protected test routes exist only in the test app; business endpoints using the dependency are added with later features. Roles are not trusted from frontend values or token claims.
- The frontend stores only the access token in local storage under `campusbite_access_token`. It validates a saved token through `/auth/me` on startup, clears the session on logout, and redirects users according to their role.
- The CUSTOMER, OWNER, and DELIVERY_PARTNER landing pages are authentication placeholders. They are not restaurant dashboards or completed role workspaces. Frontend route guards support navigation and do not replace backend authorization.

**Verification (14 November 2026):** PostgreSQL revisions `0001` and `0002` applied; an existing CUSTOMER sentinel survived revision `0002`; PostgreSQL rejected an unsupported `ADMIN` role; PostgreSQL integration tests passed (14); the full backend suite passed (53). Browser checks passed for customer registration/login, refresh persistence, logout, protected-route redirect, OWNER and DELIVERY_PARTNER login, and wrong-role redirect. `/auth/me` returned HTTP 200 on refresh; no red browser-console errors were reported.

## Milestone 3A: Restaurant and menu backend

- Public `GET /restaurants` returns a paginated list. `GET /restaurants/{restaurant_id}/menu-items` returns available menu items by default and supports case-insensitive partial name search plus inclusive `min_price` and `max_price` filters.
- OWNER-only `GET` and `PATCH /owner/restaurant` resolve the restaurant from the authenticated owner account. Owners can view, add and update menu items through `GET /owner/menu-items`, `POST /owner/menu-items`, and `PATCH /owner/menu-items/{menu_item_id}`. Owner menu responses include available and unavailable dishes. There is no hard-delete endpoint; availability can be changed with `is_available`.
- All list endpoints use `page` and `page_size` pagination (default page size 10, maximum 100). Protected routes validate the current account and role in the backend.
- The explicit demo seed command is `python -m app.seed_demo` from `backend`. It creates three fictional sample restaurants with five dishes each, three owner accounts and two delivery-partner accounts. It does not run on application startup. Exact existing seed data is left unchanged on reruns; conflicting or edited seed records cause the operation to stop without committing changes.
- Demo accounts are for local development only. All five accounts use the password `CampusBite-Local-Demo-2026!`:

  | Role | Demo email |
  | --- | --- |
  | OWNER | `owner1@campusbite.local` |
  | OWNER | `owner2@campusbite.local` |
  | OWNER | `owner3@campusbite.local` |
  | DELIVERY_PARTNER | `delivery1@campusbite.local` |
  | DELIVERY_PARTNER | `delivery2@campusbite.local` |

  These fictional credentials must not be reused outside a local demo.

## Run locally

1. Copy `.env.example` to `.env`. Set `JWT_SECRET_KEY` to a private random value of at least 32 bytes, and keep `.env` out of source control. Set `FRONTEND_ORIGIN` to the exact origin used by the browser, normally `http://localhost:5173`.
2. Start PostgreSQL, build the backend, apply the migrations, and start the API:

   ```powershell
   docker compose up -d db
   docker compose build backend
   docker compose run --rm backend alembic upgrade head
   docker compose up -d backend
   ```

   The API is at `http://localhost:8000`; health and API documentation are at `/health` and `/docs`.
3. Start the frontend in another terminal:

   ```powershell
   cd frontend
   npm ci
   $env:VITE_API_BASE_URL = "http://localhost:8000"
   npm run dev -- --host localhost --port 5173 --strictPort
   ```

   Open `http://localhost:5173`. `VITE_API_BASE_URL` is the backend origin (for example, `http://localhost:8000`), without an `/api` path prefix. The frontend defaults to that origin if the variable is unset.

To stop the Compose services, run `docker compose down`. Adding `-v` deletes the local PostgreSQL volume and its data; use it only when intentionally resetting that local database.

## Backend tests

Create a local Python environment and install the declared development requirements:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Authentication and authorization tests use an in-memory SQLite fixture. Security tests are unit-level, and the CORS preflight test does not access a database. PostgreSQL integration tests are opt-in and skip when `TEST_DATABASE_URL` is not set.

For PostgreSQL integration tests, start a separate disposable PostgreSQL database on loopback port `55432`, with database `campusbite_stage2d` and user `campusbite_test`. Do not point these tests at the regular development database. Apply migrations manually to that test database first; test fixtures do not migrate, create, or drop tables. Its Alembic revision must already be `0002_user_role_check`.

Set `TEST_DATABASE_URL` to that database’s connection URL and run:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://campusbite_test:<temporary-password>@127.0.0.1:55432/campusbite_stage2d"
```

Replace `<temporary-password>` with the disposable database password. When manually applying migrations to a fresh test database, set `DATABASE_URL` to that same test URL first. From `backend`, run:

```powershell
$env:DATABASE_URL = $env:TEST_DATABASE_URL
python -m alembic upgrade head
python -m pytest -q tests/test_postgres_integration.py
python -m pytest -q
```

The integration fixture accepts only PostgreSQL URLs for that loopback host, port, database, and user. It uses the explicit `TEST_DATABASE_URL`, not `DATABASE_URL` or `.env`, and rolls back test data after each test.

To verify the frontend production bundle, run `npm run build` from `frontend` after installing the locked packages with `npm ci`.

## Configuration and remaining milestones

`.env.example` lists database, JWT, optional OpenAI, and frontend-origin settings. It contains placeholders; keep actual secrets in the ignored `.env` file. `OPENAI_API_KEY` and `OPENAI_MODEL` enable the optional customer order-insights integration. If either is unavailable, the insights API returns a clear unavailable message and the rest of CampusBite remains usable.

## Milestone 8: AI-powered customer order insights

- CUSTOMER accounts can ask stateless questions through `POST /insights/orders`. Each request independently loads only the authenticated customer's order history; no chat history is stored.
- The backend calculates order counts, item summaries, gross successful payments, voided amounts, refunded amounts, and net spending from order and payment records. It uses historical order-item price snapshots, and computes net spending as gross successful payments minus voided amounts minus refunded amounts.
- Verified facts are returned separately from the AI explanation. The frontend displays both, labels the backend-calculated figures, and provides example questions, loading, error, and retry states at `/order-insights`.
- OpenAI access stays in the backend. Configure `OPENAI_API_KEY` and `OPENAI_MODEL` locally to enable answers. The app does not require these values to run other features.
- Backend tests mock the provider; automated tests do not make billable OpenAI requests. From `backend`, run `python -m pytest -q tests/test_order_insights.py` for the focused test module or `python -m pytest -q` for the full suite.

AI explanations are not authoritative for financial figures; use the separately displayed verified facts for exact amounts and counts. No embeddings, vector database, RAG, persistent conversation history, or database schema change is used for this feature.
