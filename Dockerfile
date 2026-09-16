# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 -- build the React bundle
# ---------------------------------------------------------------------------
# The bundle is a plain static build; nothing in the runtime image needs Node,
# so the whole toolchain is thrown away with this stage.
FROM node:22-slim AS frontend

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Deliberately no PUBLIC_PATH: webpack already emits into `dist/assets/` with
# publicPath "/", so the shell asks for "/assets/main.<hash>.js" literally --
# which is exactly what Django's STATIC_URL serves. Setting PUBLIC_PATH here
# would double the prefix to "/assets/assets/...".
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2 -- Django, serving both /api/* and the bundle
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
# gunicorn is a deployment concern, not an application dependency, so it is
# installed here rather than in requirements.txt.
RUN pip install --no-cache-dir -r backend/requirements.txt "gunicorn>=23,<24"

COPY backend/ backend/
# settings.py derives FRONTEND_DIST from `BASE_DIR.parent / "frontend" / "dist"`,
# so the repository's directory layout has to survive into the image.
COPY --from=frontend /build/frontend/dist/ frontend/dist/

WORKDIR /app/backend

# STATICFILES_DIRS is only populated when frontend/dist/assets exists, so this
# has to run after the COPY above. The build-time key is a throwaway: it exists
# only because importing settings with DEBUG off demands one, and nothing
# signed during the build outlives it -- the container gets the real key from
# the environment.
RUN DJANGO_SECRET_KEY=build-only-not-a-secret \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

RUN useradd --system --create-home --uid 10001 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# One process, many threads. The dashboard caches its Bubble snapshot in
# LocMem, which is per-process: a second worker would hold a second snapshot
# and could answer the same filter with different numbers. Threads share it,
# and the work is I/O-bound on Bubble anyway. Adding REDIS_URL is what makes
# multiple workers safe (see settings.CACHES).
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "gthread", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
