"""Applying the filter bar to the deal rows.

The snapshot is pulled from Bubble once and filtered in memory per request:
the whole history is ~13k deals, small enough that filtering it is cheaper than
a round trip, and it means changing a filter never waits on Bubble.

Filtering is on deals, not invoices. A deal is the unit the dashboard counts as
a shipment, and every invoice reaches the aggregations through its deal, so
selecting deals selects a consistent slice of both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import schema as S
from .dataset import Dataset, Row, parse_date

ALL = "all"

#: What the deal-status filter selects when the request does not say.
#: The snapshot carries every status, but the dashboard is about completed
#: business, so an unfiltered request must not start counting cancelled deals
#: as revenue.
DEFAULT_DEAL_STATUS = S.DEAL_STATUS_LIVE

#: Invoice states the status filter can express. "Partially Paid" and
#: "Disputed" are in the React enum but have no counterpart in Bubble — there
#: is no partial-settlement or dispute field on `Deal_invoice` — so selecting
#: them matches nothing rather than quietly behaving like "Open".
STATUS_OPEN = "Open"
STATUS_OVERDUE = "Overdue"
STATUS_PAID = "Paid"


@dataclass(frozen=True, slots=True)
class Filters:
    """Validated filter state, built by `params.parse_filters`."""

    date_from: date
    date_to: date
    #: Selected broker names; empty means every broker.
    brokers: tuple[str, ...] = ()
    #: Selected customer names; empty means every customer.
    customers: tuple[str, ...] = ()
    status: str = ALL
    #: Bubble's own `Status` on the deal ("Release money", "Cancelled", ...);
    #: empty means every status. Distinct from `status` above, which is about
    #: the invoice.
    deal_statuses: tuple[str, ...] = (DEFAULT_DEAL_STATUS,)
    period: str = "custom"

    def cache_key_part(self) -> str:
        """Mirrors `filterKey` in `frontend/src/lib/api.ts`.

        `period` is deliberately absent: it only names how the dates were
        chosen, so two requests differing in nothing but the preset label would
        otherwise miss a cache entry that answers both.
        """
        return "|".join([
            self.date_from.isoformat(), self.date_to.isoformat(),
            ",".join(self.brokers) or ALL, ",".join(self.customers) or ALL,
            self.status, ",".join(self.deal_statuses) or ALL,
        ])


def apply_filters(ds: Dataset, f: Filters) -> tuple[Row, ...]:
    """Select the deals a filter set describes."""
    broker_ids = _broker_ids(ds, f.brokers)
    customer_ids = _customer_ids(ds, f.customers)
    deal_statuses = set(f.deal_statuses)

    def keep(deal: Row) -> bool:
        when = parse_date(deal.get(S.DEAL_DATE))
        if when is None or when < f.date_from or when > f.date_to:
            return False
        if broker_ids is not None and not broker_ids.intersection(ds.brokers_of(deal)):
            return False
        if customer_ids is not None and deal.get(S.DEAL_CUSTOMER) not in customer_ids:
            return False
        if f.status != ALL and not _matches_status(deal, ds, f.status):
            return False
        if deal_statuses and deal.get(S.DEAL_STATUS) not in deal_statuses:
            return False
        return True

    return tuple(d for d in ds.deals if keep(d))


def filter_relations(ds: Dataset, f: Filters) -> tuple[Row, ...]:
    """Select the customer relations the broker and customer filters describe.

    For per-customer facts that are not tied to a deal (credit limits). A
    customer matches the broker filter if a selected broker held any role on
    any of its deals, ever -- whatever the deal's date or status, since the
    facts shown are current rather than per period.
    """
    broker_ids = _broker_ids(ds, f.brokers)
    customer_ids = _customer_ids(ds, f.customers)
    worked_with = None if broker_ids is None else {
        deal.get(S.DEAL_CUSTOMER)
        for deal in ds.deals
        if broker_ids.intersection(ds.brokers_of(deal))
    }

    def keep(rel: Row) -> bool:
        rid = rel.get(S.RELATION_ID)
        if worked_with is not None and rid not in worked_with:
            return False
        if customer_ids is not None and rid not in customer_ids:
            return False
        return True

    return tuple(r for r in ds.relations if keep(r))


def _broker_ids(ds: Dataset, brokers: tuple[str, ...]) -> set[str] | None:
    """User ids for the selected broker names, or None for "no broker filter".

    A deal is kept when any of its brokers is selected. Names rather than ids
    cross the wire because that is what the filter bar shows; two staff members
    sharing a display name both match, which is the honest reading of picking
    that name.
    """
    if not brokers:
        return None
    wanted = set(brokers)
    return {uid for uid, name in ds.user_name.items() if name in wanted}


def _customer_ids(ds: Dataset, customers: tuple[str, ...]) -> set[str] | None:
    if not customers:
        return None
    wanted = set(customers)
    return {cid for cid, name in ds.customer_name.items() if name in wanted}


def _matches_status(deal: Row, ds: Dataset, status: str) -> bool:
    invoices = ds.invoices_of_deal.get(deal.get(S.DEAL_ID), ())
    if not invoices:
        return False
    if status == STATUS_OPEN:
        return any(ds.is_open(i) for i in invoices)
    if status == STATUS_OVERDUE:
        return any(ds.days_overdue(i) > 0 for i in invoices)
    if status == STATUS_PAID:
        return not any(ds.is_open(i) for i in invoices)
    return False
