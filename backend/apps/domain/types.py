"""Domain records.

This project deliberately has **no Django models**: the system of record is the
Bubble.io database and Django owns none of the persistence. The shapes below are
frozen dataclasses — a typed in-memory representation of a Bubble row after
`apps.bubble.mappers` has normalised it.

Field names mirror `frontend/src/lib/mock-data.ts` (`Invoice`) so the contract is
readable from either side; the snake_case -> camelCase flip happens once, in the
API serializers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class InvoiceStatus(str, Enum):
    OPEN = "Open"
    PAID = "Paid"
    PARTIALLY_PAID = "Partially Paid"
    OVERDUE = "Overdue"
    DISPUTED = "Disputed"


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"


class FinancingStatus(str, Enum):
    ACTIVE = "Active"
    SETTLED = "Settled"
    PENDING = "Pending"


class PaymentStatus(str, Enum):
    PAID = "Paid"
    OPEN = "Open"
    OVERDUE = "Overdue"


@dataclass(frozen=True, slots=True)
class Invoice:
    """One invoice / shipment line as the dashboard understands it.

    Frozen because the dataset is shared across requests via the cache layer —
    an accidental mutation in one request must not leak into the next.
    """

    invoice_number: str
    customer: str
    customer_id: str
    broker: str
    shipment_id: str
    invoice_date: date
    due_date: date
    payment_terms: int
    revenue: float
    cost: float
    margin: float
    outstanding_amount: float
    invoice_amount: float
    status: InvoiceStatus
    currency: Currency = Currency.EUR
    financed_by_finqle: bool = False
    financing_status: FinancingStatus | None = None
    financed_amount: float | None = None
    financing_cost: float | None = None
    payment_status: PaymentStatus | None = None

    # --- derived helpers -------------------------------------------------
    # Mirrors daysOverdue()/isOverdue() in frontend/src/lib/mock-data.ts.

    def days_overdue(self, today: date) -> int:
        if self.outstanding_amount <= 0:
            return 0
        delta = (today - self.due_date).days
        return delta if delta > 0 else 0

    def is_overdue(self, today: date) -> bool:
        return self.outstanding_amount > 0 and self.due_date < today


@dataclass(frozen=True, slots=True)
class Dataset:
    """The full invoice set plus the reference date every calculation uses.

    `as_of` is carried explicitly rather than read from the clock inside the
    aggregations: overdue maths must be reproducible, and a cached dataset must
    not silently change meaning as the day rolls over.
    """

    invoices: tuple[Invoice, ...]
    as_of: date
    fetched_at: str | None = None
    source: str = "bubble"

    @property
    def brokers(self) -> list[str]:
        return sorted({i.broker for i in self.invoices})

    @property
    def customers(self) -> list[str]:
        return sorted({i.customer for i in self.invoices})
