"""Bubble row -> `apps.domain.types.Invoice`.

This is the *only* place that knows Bubble's field names. Bubble fields are
user-named ("Invoice Date", "Financed by Finqle") and change when someone edits
the app, so the mapping is data, not code: `settings.BUBBLE["FIELD_MAP"]` holds
it and can be overridden per environment without a deploy.

Two rules keep the dashboard honest:

* Missing optional fields become `None`/0, never an exception.
* A row missing an *identifying* field (invoice number, dates) is dropped and
  logged -- one malformed record must not take down the whole cockpit.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable

from django.conf import settings

from apps.domain.types import (
    Currency,
    FinancingStatus,
    Invoice,
    InvoiceStatus,
    PaymentStatus,
)

logger = logging.getLogger(__name__)

# Default Bubble field names -> Invoice attributes. Override per environment via
# BUBBLE_FIELD_MAP (JSON) so a Bubble rename is a config change, not a release.
DEFAULT_FIELD_MAP: dict[str, str] = {
    "invoice_number": "Invoice Number",
    "customer": "Customer Name",
    "customer_id": "Customer ID",
    "broker": "Broker",
    "shipment_id": "Shipment ID",
    "invoice_date": "Invoice Date",
    "due_date": "Due Date",
    "payment_terms": "Payment Terms",
    "revenue": "Revenue",
    "cost": "Cost",
    "margin": "Margin",
    "outstanding_amount": "Outstanding Amount",
    "invoice_amount": "Invoice Amount",
    "status": "Status",
    "currency": "Currency",
    "financed_by_finqle": "Financed by Finqle",
    "financing_status": "Financing Status",
    "financed_amount": "Financed Amount",
    "financing_cost": "Financing Cost",
    "payment_status": "Payment Status",
}

REQUIRED = ("invoice_number", "invoice_date", "due_date")


def field_map() -> dict[str, str]:
    return {**DEFAULT_FIELD_MAP, **settings.BUBBLE.get("FIELD_MAP", {})}


# -- coercion helpers ------------------------------------------------------

def _as_date(value: Any) -> date | None:
    """Bubble emits ISO-8601 with a Z suffix, or sometimes a plain date."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    return int(_as_float(value, default))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def _as_enum(enum_cls: Any, value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return enum_cls(str(value).strip())
    except ValueError:
        logger.debug("Unknown %s value from Bubble: %r", enum_cls.__name__, value)
        return default


# -- mapping ---------------------------------------------------------------

def map_invoice(row: dict[str, Any]) -> Invoice | None:
    """Map one Bubble row. Returns None (and logs) if the row is unusable."""
    fm = field_map()

    def get(attr: str) -> Any:
        return row.get(fm[attr])

    values = {attr: get(attr) for attr in fm}

    invoice_date = _as_date(values["invoice_date"])
    due_date = _as_date(values["due_date"])
    invoice_number = values["invoice_number"]

    if not invoice_number or invoice_date is None or due_date is None:
        logger.warning(
            "Skipping Bubble row %s: missing one of %s",
            row.get("_id", "<no id>"), ", ".join(REQUIRED),
        )
        return None

    revenue = _as_float(values["revenue"])
    cost = _as_float(values["cost"])
    # Margin is derivable; trust Bubble when it is present, derive when it is not.
    margin = _as_float(values["margin"], revenue - cost)
    invoice_amount = _as_float(values["invoice_amount"], revenue)
    financed = _as_bool(values["financed_by_finqle"])

    return Invoice(
        invoice_number=str(invoice_number),
        customer=str(values["customer"] or "Unknown"),
        customer_id=str(values["customer_id"] or ""),
        broker=str(values["broker"] or "Unassigned"),
        shipment_id=str(values["shipment_id"] or ""),
        invoice_date=invoice_date,
        due_date=due_date,
        payment_terms=_as_int(values["payment_terms"], (due_date - invoice_date).days),
        revenue=revenue,
        cost=cost,
        margin=margin,
        outstanding_amount=_as_float(values["outstanding_amount"]),
        invoice_amount=invoice_amount,
        status=_as_enum(InvoiceStatus, values["status"], InvoiceStatus.OPEN),
        currency=_as_enum(Currency, values["currency"], Currency.EUR),
        financed_by_finqle=financed,
        financing_status=_as_enum(FinancingStatus, values["financing_status"]) if financed else None,
        financed_amount=_as_float(values["financed_amount"]) if financed else None,
        financing_cost=_as_float(values["financing_cost"]) if financed else None,
        payment_status=_as_enum(PaymentStatus, values["payment_status"]),
    )


def map_invoices(rows: Iterable[dict[str, Any]]) -> tuple[Invoice, ...]:
    """Map a stream of Bubble rows, dropping (and counting) the unusable ones."""
    mapped: list[Invoice] = []
    skipped = 0
    for row in rows:
        invoice = map_invoice(row)
        if invoice is None:
            skipped += 1
        else:
            mapped.append(invoice)
    if skipped:
        logger.warning("Dropped %s malformed Bubble rows out of %s",
                       skipped, skipped + len(mapped))
    return tuple(mapped)
