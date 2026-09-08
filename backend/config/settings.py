"""Settings for the Brocarga Finance Performance Cockpit backend.

Shape of the system:

    React SPA  ->  Django (this project)  ->  integrations.bubble  ->  Bubble.io

There is **no database**. Bubble is the system of record; Django owns none of
the persistence, so `DATABASES` is empty and `INSTALLED_APPS` deliberately
excludes admin/auth/sessions/contenttypes — every one of those needs an ORM we
do not have. What Django owns instead is the filtering, the aggregation and the
Bubble credentials, none of which may ever reach the browser.

Configuration comes from the environment (see `.env.example`). A tiny `.env`
reader is built in so the project needs no settings library beyond Django and
`requests`.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
REPO_ROOT = BASE_DIR.parent                                # repository root
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"            # `npm run build` output


# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------

def _load_dotenv(path: Path) -> None:
    """Populate `os.environ` from a KEY=VALUE file, without overriding it.

    Real environment variables always win, so a container's injected secrets
    are never shadowed by a stale `.env` that got baked into an image.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")
_load_dotenv(REPO_ROOT / ".env")


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value in (None, "") else value


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(str(env(name, str(default))))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(str(env(name, str(default))))
    except ValueError:
        return default


def env_list(name: str, default: list[str]) -> list[str]:
    value = env(name)
    return default if value is None else [p.strip() for p in value.split(",") if p.strip()]


def env_json(name: str, default: dict) -> dict:
    """Read a JSON object from the environment; a bad value is a hard error.

    Used for the Bubble field maps. Silently falling back to the defaults after
    someone fat-fingers the JSON would produce a dashboard full of zeros with
    no clue why, so this raises instead.
    """
    value = env(name)
    if value is None:
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ImproperlyConfigured(f"{name} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ImproperlyConfigured(f"{name} must be a JSON object, got {type(parsed).__name__}")
    return parsed


def env_date(name: str) -> date | None:
    value = env(name)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an ISO date (YYYY-MM-DD): {exc}") from exc


# --------------------------------------------------------------------------
# Core Django
# --------------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-insecure-key" if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"] if DEBUG else [])

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.gzip.GZipMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# No template engine: the only HTML served is the pre-built SPA shell, which is
# streamed verbatim from disk rather than rendered.
TEMPLATES: list[dict] = []

# No ORM. Any accidental model or `.objects` call fails loudly rather than
# quietly inventing a second system of record alongside Bubble.
DATABASES: dict = {}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Europe/Amsterdam")
USE_I18N = False
USE_TZ = True

APPEND_SLASH = True


# --------------------------------------------------------------------------
# Static files / the built SPA
# --------------------------------------------------------------------------

# Webpack emits the bundle into `dist/assets/` and builds it with
# `publicPath: "/"`, so the shell HTML asks for `/assets/main.<hash>.js`
# literally. STATIC_URL therefore *is* `/assets/` — serving the same files
# under `/static/` would leave those requests to the SPA catch-all, which
# would answer a JavaScript request with the HTML shell and a blank page.
STATIC_URL = env("DJANGO_STATIC_URL", "/assets/")
STATIC_ROOT = BASE_DIR / "staticfiles"
# `npm run build` writes frontend/dist; in production `collectstatic` copies it
# here. If the bundle has not been built yet the directory is simply absent and
# the API still works — `/` then explains what to run.
STATICFILES_DIRS = [FRONTEND_DIST / "assets"] if (FRONTEND_DIST / "assets").is_dir() else []


# --------------------------------------------------------------------------
# Security (only meaningful behind TLS in production)
# --------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", False)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# In dev the SPA runs on webpack-dev-server:8080 and proxies /api to :8000, so
# the browser only ever sees one origin and no CORS handling is needed here.


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------
# A full Bubble pull is thousands of rows over many paginated calls. Every
# dashboard request reuses one cached snapshot instead; the aggregations
# themselves are fast enough to run per request.

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "brocarga-dashboard",
        "TIMEOUT": env_int("CACHE_TTL", 300),
        "OPTIONS": {"MAX_ENTRIES": 256},
    }
}
if env("REDIS_URL"):
    # Multi-worker deploys want a shared snapshot; per-process LocMem would let
    # two workers answer the same filter with different numbers.
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
        "TIMEOUT": env_int("CACHE_TTL", 300),
    }


# --------------------------------------------------------------------------
# Bubble integration
# --------------------------------------------------------------------------
# PROVIDER:
#   "bubble" -- talk to the real Bubble app (needs BUBBLE_BASE_URL + token)
#   "sample" -- deterministic in-process dataset, no credentials, no network
#
# `sample` is for local dev, CI and demos. It is never a silent fallback:
# /api/health/ reports the live provider so a misconfigured deploy shows up as
# a wrong answer to a direct question rather than as plausible fiction.

BUBBLE = {
    "PROVIDER": (env("BUBBLE_PROVIDER", "sample") or "sample").strip().lower(),
    "BASE_URL": env("BUBBLE_BASE_URL", ""),
    "API_TOKEN": env("BUBBLE_API_TOKEN", ""),
    "TIMEOUT": env_float("BUBBLE_TIMEOUT", 30.0),
    "MAX_RETRIES": env_int("BUBBLE_MAX_RETRIES", 3),
    # Hard ceiling on one pull, so a runaway Bubble table cannot exhaust memory.
    "MAX_ROWS": env_int("BUBBLE_MAX_ROWS", 100_000),
    # How far back to ask Bubble for transactions. The dashboard's widest
    # preset is "last year"; the extra months keep month-over-month deltas at
    # the edge of that window honest.
    "HISTORY_DAYS": env_int("BUBBLE_HISTORY_DAYS", 550),
    "CACHE_TTL": env_int("BUBBLE_CACHE_TTL", 300),
    # Bubble data type names ("things"). Renaming a type in Bubble is a config
    # change here, not a deploy.
    "TYPES": {
        "customer": env("BUBBLE_TYPE_CUSTOMER", "customer"),
        "broker": env("BUBBLE_TYPE_BROKER", "broker"),
        "transaction": env("BUBBLE_TYPE_TRANSACTION", "transaction"),
    },
    # Per-entity overrides of the DEFAULT_FIELD_MAP in each integration module.
    # e.g. BUBBLE_FIELD_MAP='{"transaction": {"revenue": "Turnover"}}'
    "FIELD_MAP": env_json("BUBBLE_FIELD_MAP", {}),
}

if BUBBLE["PROVIDER"] not in {"bubble", "sample"}:
    raise ImproperlyConfigured(
        f"BUBBLE_PROVIDER must be 'bubble' or 'sample', got {BUBBLE['PROVIDER']!r}"
    )
if BUBBLE["PROVIDER"] == "bubble" and not (BUBBLE["BASE_URL"] and BUBBLE["API_TOKEN"]):
    raise ImproperlyConfigured(
        "BUBBLE_PROVIDER=bubble requires both BUBBLE_BASE_URL and BUBBLE_API_TOKEN."
    )

# The reference date every overdue calculation uses. Pinning it keeps a cached
# snapshot from silently changing meaning as midnight passes mid-session; the
# sample provider pins it to its own generated "today" so the demo numbers are
# stable forever.
DASHBOARD = {
    "AS_OF": env_date("DASHBOARD_AS_OF"),
    # Rows returned in the receivables worklist table. Full extracts go through
    # /api/transactions/export/ instead of inflating every tab response.
    "TABLE_LIMIT": env_int("DASHBOARD_TABLE_LIMIT", 500),
    "EXPORT_LIMIT": env_int("DASHBOARD_EXPORT_LIMIT", 50_000),
}


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)-7s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "integrations.bubble": {"level": env("LOG_LEVEL_BUBBLE", "INFO")},
        "django.request": {"level": "WARNING", "propagate": True},
    },
}
