# CampusBite 🍔

CampusBite is an academic capstone project for restaurant ordering and delivery. The required V1 scope is described in the supplied project problem statement; this repository is being implemented in small, reviewable feature milestones.

## Technology

- Frontend: React, JavaScript, Vite, React Router
- Backend: Python, FastAPI, Pydantic Settings, SQLAlchemy
- Database: PostgreSQL
- Database migrations: Alembic
- Local backend/database: Docker Compose

## Milestone 1: Project foundation

The current foundation includes the React app shell, FastAPI health endpoint, initial relational models, Alembic migration setup, and local PostgreSQL/backend containers. Product features are added in later milestones.

**Milestone 1 verification (13 November 2026):** Docker Compose configuration validated; backend image built; PostgreSQL and FastAPI containers started and reported healthy; migration `0001_initial_schema` applied to PostgreSQL; all nine application tables were present; `/health` and `/docs` returned HTTP 200. This verifies the project foundation only; product workflows remain for later milestones.

## Run locally

1. Copy `.env.example` to `.env` and replace the local placeholder values as needed. Do not commit `.env`.
2. Start PostgreSQL:

   ```powershell
   docker compose up -d db
   ```

3. Build the backend image and apply the database migration:

   ```powershell
   docker compose build backend
   docker compose run --rm backend alembic upgrade head
   ```

4. Start the API:

   ```powershell
   docker compose up -d backend
   ```

   The API health endpoint is `http://localhost:8000/health`; interactive API docs are at `http://localhost:8000/docs`.

5. In a second terminal, run the React development server:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

   Vite prints the local frontend URL (normally `http://localhost:5173`).

To stop the services, run `docker compose down`. To also delete the local database volume, run `docker compose down -v`.

## Configuration

`.env.example` lists the local PostgreSQL connection, JWT settings, optional OpenAI settings, and frontend origin. The example contains placeholders only. Keep real API keys, passwords, and secrets in the untracked `.env` file.

## Repository status

The implementation is in progress. The project will be completed against every mandatory feature in the capstone problem statement. Seed data, demo credentials, authentication, ordering, dashboards, refunds, AI insights, reminders, and full feature documentation are added in later milestones.
