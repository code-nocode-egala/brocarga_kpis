"""Getting the four Bubble tables, and holding on to them.

A full pull is roughly 13k deals, 12k invoices, 700 relations and 10 users over
~270 paginated calls — twenty seconds of Bubble's time. Doing that per request
would make the dashboard unusable, so one snapshot is fetched, cached for
`BUBBLE["CACHE_TTL"]` seconds and shared by every filter combination. Filtering
and aggregating are milliseconds on top of it.

The snapshot is process-wide, not per session. That is deliberate: everyone
looking at the cockpit at the same moment should be looking at the same numbers.

Constraints are pushed down to Bubble where they narrow the pull for everybody
(draft invoices, external users). Deal *status* is deliberately no longer among
them: the filter bar can now select any status, so every status has to be in the
snapshot -- and all of them together are only ~1.4k rows on top of the 12k that
are `Release money`. The date window is not pushed down either: the filter bar
moves it constantly and re-pulling per window would give up the shared cache for
no gain.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.bubble.client import BubbleClient

from . import schema as S
from .dataset import Dataset, Row, parse_date

logger = logging.getLogger(__name__)

CACHE_KEY = "dashboard:snapshot:v1"

#: Serialises concurrent misses. Without it, three browser tabs refreshing after
#: the TTL expires each start their own twenty-second pull of the same data.
_fetch_lock = threading.Lock()


def _conf() -> dict[str, Any]:
    return settings.BUBBLE


def get_dataset(force: bool = False) -> Dataset:
    """The current snapshot, fetching it if the cache is cold."""
    if not force:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    with _fetch_lock:
        # Another thread may have filled the cache while we waited for the lock.
        if not force:
            cached = cache.get(CACHE_KEY)
            if cached is not None:
                return cached

        dataset = _load()
        cache.set(CACHE_KEY, dataset, _conf()["CACHE_TTL"])
        return dataset


def _load() -> Dataset:
    provider = _conf()["PROVIDER"]
    if provider == "sample":
        from .sample import generate

        deals, users, invoices, relations = generate()
        logger.info("Loaded sample dataset: %d deals, %d invoices", len(deals), len(invoices))
    else:
        deals, users, invoices, relations = _fetch_from_bubble()

    return Dataset(
        deals=tuple(deals),
        users=tuple(users),
        invoices=tuple(invoices),
        relations=tuple(relations),
        as_of=_as_of(deals),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        source=provider,
    )


def _fetch_from_bubble() -> tuple[list[Row], list[Row], list[Row], list[Row]]:
    conf = _conf()
    client = BubbleClient(
        conf["BASE_URL"], conf["API_TOKEN"], conf["TIMEOUT"], conf["MAX_RETRIES"]
    )
    max_rows = conf["MAX_ROWS"]

    def pull(type_name: str, constraints: list[dict[str, Any]]) -> list[Row]:
        rows = list(client.list_objects(type_name, constraints=constraints, max_rows=max_rows))
        logger.info("Bubble %s: %d rows", type_name, len(rows))
        if len(rows) >= max_rows:
            # Silently truncating would show a plausible but wrong total.
            logger.warning(
                "Bubble %s hit BUBBLE_MAX_ROWS (%d); the dashboard is showing a "
                "partial dataset. Raise BUBBLE_MAX_ROWS.", type_name, max_rows,
            )
        return rows

    # Every status, so `Filters.deal_status` has something to choose between.
    # The default filter value still narrows to DEAL_STATUS_LIVE, so what the
    # dashboard shows out of the box is unchanged.
    deals = pull(S.DEAL, [])
    users = pull(S.USER, [
        {"key": S.USER_LEVEL, "constraint_type": "not equal", "value": S.USER_LEVEL_EXTERNAL},
    ])
    # Final invoices, plus every OPEN one whatever its final/wrong flag: an
    # open invoice is money owed whether or not it was marked final. Bubble
    # constraints only AND together, hence two pulls merged on `_id`.
    final = pull(S.INVOICE, [
        {"key": S.INVOICE_FINAL_FIELD, "constraint_type": "equals",
         "value": S.INVOICE_FINAL_VALUE},
    ])
    open_ = pull(S.INVOICE, [
        {"key": S.INVOICE_FINQLE_STATUS, "constraint_type": "equals", "value": "OPEN"},
    ])
    seen = {inv.get(S.INVOICE_ID) for inv in final}
    invoices = final + [inv for inv in open_ if inv.get(S.INVOICE_ID) not in seen]
    relations = pull(S.RELATION, [])
    return deals, users, invoices, relations


def _as_of(deals: list[Row]) -> date:
    """The reference date every overdue calculation is anchored to.

    `DASHBOARD_AS_OF` pins it explicitly. Otherwise it is today — but never
    earlier than the newest deal in the data, so a clock skew or a stale
    container cannot make the freshest shipments fall outside every period
    preset and disappear from the dashboard.
    """
    pinned = settings.DASHBOARD["AS_OF"]
    if pinned:
        return pinned
    today = datetime.now(timezone.utc).date()
    newest = max(
        (d for d in (parse_date(row.get(S.DEAL_DATE)) for row in deals) if d),
        default=today,
    )
    return max(today, newest)
