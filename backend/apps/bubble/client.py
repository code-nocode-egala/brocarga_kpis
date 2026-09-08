"""Low-level HTTP client for the Bubble.io API.

Knows about transport only -- auth, pagination, retries, timeouts -- and returns
raw Bubble dicts. Interpretation of those dicts belongs in `mappers.py`.

Two Bubble surfaces are supported:

* **Data API** -- `GET /api/1.1/obj/<type>`; cursor paginated, max 100 rows per
  call, optional `constraints` for server-side filtering.
* **Workflow API** -- `GET|POST /api/1.1/wf/<endpoint>`; used when a Bubble
  backend workflow returns a pre-shaped payload instead of raw rows.

The Bubble API token is a *private* key with full data access. It is read from
the environment and never leaves the server: the browser talks only to Django.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator, Sequence

import requests
from django.conf import settings

from .exceptions import BubbleAuthError, BubbleRateLimited, BubbleUnavailable

logger = logging.getLogger(__name__)

# Bubble caps the Data API at 100 objects per call regardless of what you ask.
MAX_PAGE_SIZE = 100


class BubbleClient:
    """Thin, retrying wrapper around the Bubble REST API.

    Instantiate per request cycle (it is cheap) or reuse -- the underlying
    `requests.Session` is safe for sequential use and keeps the TLS connection
    warm across the many pages a full invoice sync needs.
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        self.base_url = (base_url).rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "User-Agent": "brocarga-kpis-backend/1.0",
        })

    # -- public API ------------------------------------------------------

    def list_objects(
        self,
        type_name: str,
        constraints: Sequence[dict[str, Any]] | None = None,
        sort_field: str | None = None,
        descending: bool = False,
        page_size: int = MAX_PAGE_SIZE,
        max_rows: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every row of a Bubble data type, following the cursor.

        `constraints` is Bubble's own filter format, e.g.::

            [{"key": "Invoice Date", "constraint_type": "greater than",
              "value": "2025-01-01"}]

        Pushing the date window down to Bubble keeps the sync small; anything
        Bubble cannot express is filtered in `apps.domain.filters` instead.
        """
        path = f"/api/1.1/obj/{type_name}"
        cursor = 0
        yielded = 0

        while True:
            params: dict[str, Any] = {
                "cursor": cursor,
                "limit": min(page_size, MAX_PAGE_SIZE),
            }
            if constraints:
                params["constraints"] = json.dumps(list(constraints))
            if sort_field:
                params["sort_field"] = sort_field
                params["descending"] = "true" if descending else "false"

            payload = self._get(path, params)
            body = payload.get("response", {})
            results = body.get("results", []) or []

            for row in results:
                yield row
                yielded += 1
                if max_rows is not None and yielded >= max_rows:
                    return

            remaining = body.get("remaining", 0) or 0
            if not results or remaining <= 0:
                return
            cursor += len(results)

    # -- transport -------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", path, params)

    def _request(self, method: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Issue one request, retrying idempotent failures with backoff.

        Retries cover 429 and 5xx plus connection errors -- Bubble's rate limit
        is per app and a full sync brushes against it. 401/403 are not retried:
        a bad token will not fix itself.
        """
        url = f"{self.base_url}{path}"
        attempt = 0
        last_error: Exception | None = None

        while attempt <= self.max_retries:
            try:
                kwargs: dict[str, Any] = {"timeout": self.timeout}
                if method.upper() == "GET":
                    kwargs["params"] = params
                else:
                    kwargs["json"] = params

                response = self.session.request(method, url, **kwargs)

                if response.status_code in (401, 403):
                    raise BubbleAuthError(
                        f"Bubble rejected the API token ({response.status_code}) for {path}"
                    )
                if response.status_code == 429:
                    raise BubbleRateLimited("Bubble rate limit hit")
                if response.status_code >= 500:
                    raise BubbleUnavailable(
                        f"Bubble returned {response.status_code} for {path}"
                    )
                response.raise_for_status()
                return response.json()

            except BubbleAuthError:
                raise
            except (BubbleRateLimited, BubbleUnavailable, requests.RequestException) as exc:
                last_error = exc
                attempt += 1
                if attempt > self.max_retries:
                    break
                delay = min(2 ** attempt * 0.5, 8.0)
                logger.warning(
                    "Bubble %s %s failed (%s); retry %s/%s in %.1fs",
                    method, path, exc, attempt, self.max_retries, delay,
                )
                time.sleep(delay)

        raise BubbleUnavailable(f"Bubble request failed after retries: {last_error}")
