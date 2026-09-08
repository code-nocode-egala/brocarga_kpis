"""The filter set the dashboard sends, and how it is applied to rows.

Ports `applyFilters` and `rangeForPreset` from the frontend
(`src/lib/dashboard-data.ts`, `src/components/dashboard/FilterBar.tsx`). Once the
UI stops shipping its own copy of the data, these become the single
implementation and the React side only sends query parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .types import Invoice, InvoiceStatus

ALL = "all"

PERIOD_PRESETS = ("day", "week", "4weeks", "month", "quarter", "year", "all", "custom")

EPOCH = date(1970, 1, 1)

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _days_in_month(year: int, month: int) -> int:
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def _shift_months(d: date, months: int) -> date:
    """Calendar-month shift that clamps to the last valid day (31 Mar -> 28 Feb)."""
    month_index = (d.year * 12 + (d.month - 1)) + months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    return date(year, month, min(d.day, _days_in_month(year, month)))


def range_for_preset(preset: str, today: date) -> tuple[date, date]:
    """Resolve a named period into an inclusive [from, to] range."""
    match preset:
        case "day":
            return today, today
        case "week":
            return today - timedelta(days=7), today
        case "4weeks":
            return today - timedelta(days=28), today
        case "month":
            return _shift_months(today, -1), today
        case "quarter":
            return _shift_months(today, -3), today
        case "year":
            return _shift_months(today, -12), today
        case "all":
            return EPOCH, today
        case _:
            return _shift_months(today, -1), today


@dataclass(frozen=True, slots=True)
class Filters:
    """Validated filter state. Built by `apps.api.params.parse_filters`."""

    date_from: date
    date_to: date
    broker: str = ALL
    customer: str = ALL
    status: str = ALL
    period: str = "custom"

    def cache_key_part(self) -> str:
        return "|".join(
            [
                self.date_from.isoformat(),
                self.date_to.isoformat(),
                self.broker,
                self.customer,
                self.status,
            ]
        )


def apply_filters(rows: tuple[Invoice, ...], f: Filters, today: date) -> tuple[Invoice, ...]:
    """Filter invoices by date range, broker, customer and status.

    `status="Overdue"` is a *computed* filter (outstanding & past due), not a
    literal match on the stored status — same rule as the frontend, so a
    partially paid invoice that is past its due date still counts as overdue.
    """

    def keep(r: Invoice) -> bool:
        if r.invoice_date < f.date_from or r.invoice_date > f.date_to:
            return False
        if f.broker != ALL and r.broker != f.broker:
            return False
        if f.customer != ALL and r.customer != f.customer:
            return False
        if f.status != ALL:
            if f.status == InvoiceStatus.OVERDUE.value:
                if not r.is_overdue(today):
                    return False
            elif r.status.value != f.status:
                return False
        return True

    return tuple(r for r in rows if keep(r))
