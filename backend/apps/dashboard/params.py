"""Reading the query string the React app sends.

The parameter names are the contract documented in `filterParams` in
`frontend/src/lib/api.ts`: `from`/`to` are inclusive ISO dates; `broker`,
`customer` and `dealStatus` may repeat, one per selected value, and any of them
set to "all" means no filter on that field; `status` uses "all" as its
no-filter sentinel; and `period` carries the preset the user picked.

An absent `broker` or `customer` means every one; an absent `dealStatus` means
the default status, not every status -- see `DEFAULT_DEAL_STATUS`.

Nothing here raises on bad input. A dashboard that 400s because a date picker
produced an empty string is worse than one that falls back to its default
window, and none of these parameters reach a query language where a malformed
value could mean anything but "ignore me".
"""

from __future__ import annotations

from datetime import date, datetime

from apps.domain.filters import range_for_preset

from .filters import ALL, DEFAULT_DEAL_STATUS, Filters

DEFAULT_PERIOD = "all"


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip()[:10]).date()
    except ValueError:
        return None


def _selected(values: list[str]) -> tuple[str, ...]:
    """Selected names for a repeatable parameter, deduplicated and sorted so the
    cache key is stable. Empty means no filter on that field.

    "all" anywhere in the list means no filter, which keeps the old
    single-value `broker=all` style of request working.
    """
    names = {v.strip() for v in values if v and v.strip()}
    if ALL in names:
        return ()
    return tuple(sorted(names))


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
        brokers=_selected(query.getlist("broker")),
        customers=_selected(query.getlist("customer")),
        status=(query.get("status") or ALL).strip() or ALL,
        # Absent means the default, not ALL -- see `DEFAULT_DEAL_STATUS`.
        deal_statuses=_selected(
            [v for v in query.getlist("dealStatus") if v.strip()] or [DEFAULT_DEAL_STATUS]
        ),
        period=period,
    )
