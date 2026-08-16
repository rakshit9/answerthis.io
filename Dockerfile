# Paper Improvement Agent — single image, single process.
#
# The app already knows how to serve its own frontend: app/main.py mounts
# ../frontend/dist when that directory exists. So the image builds the React
# app, drops the result next to the backend, and runs one uvicorn — no nginx,
# no second container, and the same code path the README's single-process
# mode uses.
#
#   docker compose up --build     → http://localhost:8000

# ---------------------------------------------------------------- frontend --
FROM node:20-alpine AS frontend

WORKDIR /build
# Copy manifests first so `npm ci` is cached until dependencies actually change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# `npm run build` is `tsc -b && vite build`, so a type error fails the image
# build rather than shipping a broken bundle.
RUN npm run build


# ----------------------------------------------------------------- runtime --
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Same ordering trick: requirements before source, so editing a .py file does
# not reinstall PyMuPDF and friends.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
# main.py resolves ../frontend/dist relative to backend/app, so the repo's
# directory shape has to survive into the image.
COPY --from=frontend /build/dist frontend/dist

# Parsed papers live here. Declared so the data survives `docker compose down`
# even if nobody mounts anything over it.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /app/backend/data \
 && chown -R app:app /app
VOLUME ["/app/backend/data"]

USER app
WORKDIR /app/backend
EXPOSE 8000

# No curl in slim, and adding one just for this is not worth a layer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
