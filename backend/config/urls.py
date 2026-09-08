"""URL map.

Every JSON endpoint lives under `/api/`, which is exactly what
`frontend/webpack.config.js` proxies to this server in development. Anything
else falls through to the SPA shell so the React app owns its own routing.

Routes are declared here rather than in an app-level `urls.py` because there is
only one app: an extra include layer would add a file without adding clarity.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.urls import path, re_path

from apps.dashboard import views

# Taken from STATIC_URL rather than written out, so changing where the bundle
# is served from cannot leave this pattern behind pointing at the old prefix.
_STATIC_PREFIX = re.escape(settings.STATIC_URL.lstrip("/"))

urlpatterns = [
    # -- operational -----------------------------------------------------
    path("api/health/", views.health, name="health"),
    # Filter-bar options: brokers, customers, statuses, the reference date.
    path("api/meta/", views.meta, name="meta"),

    # -- the whole dashboard in one response -----------------------------
    # What the React app calls. The three tabs share one filter bar, so they
    # are built from one filtered slice and sent together.
    path("api/dashboard/", views.dashboard, name="dashboard"),

    # -- the same payloads, one tab at a time ----------------------------
    path("api/dashboard/performance/", views.performance, name="performance"),
    path("api/dashboard/receivables/", views.receivables, name="receivables"),
    path("api/dashboard/customers/", views.customers, name="customers"),

    # -- full extract (the tabs carry a capped table) --------------------
    path("api/transactions/export/", views.export_transactions, name="transactions-export"),

    # -- the SPA ---------------------------------------------------------
    # Catch-all last, and explicitly not matching /api/ or the static prefix,
    # so a typo in an endpoint path returns the HTML shell only for genuine app
    # routes, a clean 404 for everything under /api/, and never the shell in
    # place of a missing asset.
    re_path(rf"^(?!api/|{_STATIC_PREFIX}).*$", views.spa_index, name="spa"),
]
