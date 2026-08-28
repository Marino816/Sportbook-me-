# Root Dockerfile for Railway/Railpack build.
#
# Railway's `rootDirectory: backend` setting is not being honored by the
# Railpack builder — it scans the repo root and sees multiple top-level
# projects (backend/, web/, mobile/, prototype/), which causes it to fail
# with "Railpack could not determine how to build the app."
#
# This Dockerfile pins the build context to `backend/` explicitly so
# Railway builds only the FastAPI backend, regardless of how the platform
# resolves the rootDirectory setting. Railway will inject the actual start
# command via the service's startCommand/PORT environment configuration,
# overriding the CMD below.

FROM python:3.11-slim

WORKDIR /app/backend

# Install system dependencies required by common Python build backends
# (e.g. psycopg2-binary, xgboost, scikit-learn) before copying source.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Only copy the backend directory — this is the build context for the app.
COPY backend/ /app/backend/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# Default command; Railway overrides this with the configured startCommand.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]
