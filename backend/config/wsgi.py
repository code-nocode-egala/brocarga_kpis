"""WSGI entrypoint (gunicorn / uWSGI).

The workload is I/O-bound on Bubble, so give the workers threads:

    gunicorn config.wsgi:application --workers 3 --threads 4 --bind 0.0.0.0:8000

With more than one worker, set REDIS_URL as well — otherwise each worker keeps
its own snapshot cache and two of them can answer the same filter with numbers
pulled at different moments.
"""

from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
