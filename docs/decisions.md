# Decisions

## 2026-11-25: Stack and mail handling (human)

- Frontend: React with TypeScript, built by Vite.
- Backend: FastAPI (Python), managed with `uv`.
- Storage: SQLite, accessed through SQLAlchemy. SQLAlchemy gives typed
  models and migrations-friendly schema definitions over the stdlib
  `sqlite3` module, at the cost of one extra dependency, which is a
  reasonable trade for a project with several related tables (profiles,
  sessions, payments, notifications).
- Packaging: one Docker image. A multi-stage build compiles the frontend,
  then copies the static output into a slim Python image that serves both
  the API (under `/api`) and the built frontend (at `/`).
- Emails (profile confirmation, session and payment notices) are written to
  a local outbox table and the server log instead of being sent, so the
  project runs with no mail service.
