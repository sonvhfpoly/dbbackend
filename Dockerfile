FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /srv

# Installed from the lockfile before app/ is copied, so this layer only
# rebuilds when dependencies actually change, not on every code edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# app/ contains main.py plus the core/ and domains/ packages it imports directly
# (e.g. `from core.database import ...`), so it must run from inside app/.
COPY app/ ./app/
WORKDIR /srv/app

RUN useradd --create-home appuser
USER appuser

ENV PATH="/srv/.venv/bin:${PATH}"

# Cloud Run sets $PORT at runtime (defaults to 8080); shell form lets it expand.
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
