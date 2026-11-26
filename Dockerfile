# syntax=docker/dockerfile:1

FROM node:22-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend
WORKDIR /app

RUN groupadd --system cm && useradd --system --gid cm --home /app cm

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /usr/local/bin/

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/app ./app
COPY --from=frontend-build /src/frontend/dist ./frontend_dist

ENV PATH="/app/.venv/bin:${PATH}" \
    CM_DB_PATH=/data/cm.sqlite3

RUN mkdir -p /data && chown -R cm:cm /app /data

USER cm
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
