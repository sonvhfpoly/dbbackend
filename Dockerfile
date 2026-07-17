FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app/ contains main.py plus the core/ and domains/ packages it imports directly
# (e.g. `from core.database import ...`), so it must run from inside app/.
COPY app/ ./app/
WORKDIR /srv/app

RUN useradd --create-home appuser
USER appuser

# Cloud Run sets $PORT at runtime (defaults to 8080); shell form lets it expand.
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
