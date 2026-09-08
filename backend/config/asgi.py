"""ASGI entrypoint (uvicorn / daphne).

The views are synchronous — `requests` blocks, and the aggregations are CPU
work — so ASGI buys nothing today. It exists so a future streaming or SSE
endpoint has somewhere to plug in.
"""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
