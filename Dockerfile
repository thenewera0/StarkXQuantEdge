# Backend image for the always-on API + schedulers (deploy to Railway / Render / Fly, NOT Vercel).
# Build context = repo root so db/migrations is available to the migrate script.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY db/ ./db/

WORKDIR /app/backend

# Apply DB migrations (idempotent) on boot, then start the API + in-process schedulers.
CMD ["sh", "-c", "python -m scripts.migrate || true; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
