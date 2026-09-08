#!/usr/bin/env python
"""Django's command-line utility for the Brocarga backend.

Run everything from `backend/`:

    python manage.py runserver 8000     # serve the API (and the built SPA)
    python manage.py check              # validate settings + Bubble config
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - startup guard
        raise ImportError(
            "Django is not importable. Activate your virtualenv and run "
            "`pip install -r requirements.txt`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
