"""Reading the query string the React app sends.

The parameter names are the contract documented in `filterParams` in
`frontend/src/lib/api.ts`: `from`/`to` are inclusive ISO dates, `broker`,
`customer` and `status` use the literal string "all" as the no-filter sentinel,
and `period` carries the preset the user picked.

Nothing here raises on bad input. A dashboard that 400s because a date picker
produced an empty string is worse than one that falls back to its default
window, and none of these parameters reach a query language where a malformed
value could mean anything but "ignore me".
"""

from __future__ import annotations

from datetime import date, datetime

from apps.domain.filters import range_for_preset

from .filters import ALL, DEFAULT_DEAL_STATUS, Filters

DEFAULT_PERIOD = "year"


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip()[:10]).date()
    except ValueError:
        return None


def parse_filters(query, as_of: date) -> Filters:
    """Build a `Filters` from a Django `request.GET`.

    `as_of` is the dataset's reference date, not today's: the filter bar clamps
    its pickers to `/api/meta/`'s `asOf`, and a preset resolved against a
    different "today" here would select a window the UI never offered.
    """
    period = (query.get("period") or DEFAULT_PERIOD).strip()
    date_from = _as_date(query.get("from"))
    date_to = _as_date(query.get("to"))

    # An explicit range wins; otherwise the preset decides. This is also what
    # rescues a half-filled range (one picker cleared) from selecting nothing.
    if date_from is None or date_to is None:
        preset = period if period != "custom" else DEFAULT_PERIOD
        date_from, date_to = range_for_preset(preset, as_of)

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    return Filters(
        date_from=date_from,
        date_to=date_to,
        broker=(query.get("broker") or ALL).strip() or ALL,
        customer=(query.get("customer") or ALL).strip() or ALL,
        status=(query.get("status") or ALL).strip() or ALL,
        # Absent means the default, not ALL -- see `DEFAULT_DEAL_STATUS`.
        deal_status=(query.get("dealStatus") or DEFAULT_DEAL_STATUS).strip()
        or DEFAULT_DEAL_STATUS,
        period=period,
    )
