"""Deterministic stand-in dataset -- a Python port of `src/lib/mock-data.ts`.

Purpose: let the backend and the whole API surface run with no Bubble
credentials (local dev, CI, demos, and the integration tests that assert the
Python aggregations match the numbers the React version produced).

It is *not* a fallback for production. `get_provider()` only selects it when
`BUBBLE_PROVIDER=mock`, and `/api/health/` reports which provider is live so a
misconfigured deploy is visible rather than quietly serving fiction.

The PRNG is the same mulberry32 with the same seed and the same call order as
the TypeScript original, so both sides generate a byte-identical dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from apps.domain.types import (
    Currency,
    FinancingStatus,
    Invoice,
    InvoiceStatus,
    PaymentStatus,
)

TODAY = date(2026, 7, 8)
SEED = 20260708
WEEKS = 78

BROKERS = ["L. van Dijk", "S. Bakker", "M. Jansen", "P. de Vries", "K. Meijer", "J. Visser"]


@dataclass(frozen=True, slots=True)
class CustomerProfile:
    name: str
    weight: int          # revenue share weight
    margin_min: float    # gross margin floor
    margin_max: float    # gross margin ceiling
    late_payer_bias: float  # 0 = disciplined, 1 = chronic slow payer


CUSTOMER_PROFILES: tuple[CustomerProfile, ...] = (
    CustomerProfile("Barry Callebaut Belgium B.V.", 22, 0.06, 0.11, 0.15),
    CustomerProfile("Sarens Nv", 16, 0.08, 0.14, 0.75),
    CustomerProfile("CP Benelux Logistics B.V.", 12, 0.18, 0.26, 0.20),
    CustomerProfile("CTS International", 10, 0.05, 0.10, 0.85),
    CustomerProfile("Dyness Europe B.V.", 9, 0.20, 0.28, 0.10),
    CustomerProfile("E Plus Logistics B.V.", 8, 0.10, 0.16, 0.55),
    CustomerProfile("ACE Filters Europe", 6, 0.22, 0.30, 0.30),
    CustomerProfile("Wiltec B.V.", 5, 0.14, 0.20, 0.05),
    CustomerProfile("H.M. Verploegen", 5, 0.04, 0.09, 0.40),
    CustomerProfile("Brandmerchandising B.V.", 4, 0.24, 0.34, 0.65),
    CustomerProfile("Meridian Connect", 3, 0.16, 0.24, 0.90),
)

CUSTOMERS = [p.name for p in CUSTOMER_PROFILES]
PROFILE_BY_NAME = {p.name: p for p in CUSTOMER_PROFILES}
TOTAL_WEIGHT = sum(p.weight for p in CUSTOMER_PROFILES)

PAYMENT_TERMS = [14, 30, 30, 30, 45, 60]

_MASK = 0xFFFFFFFF


def _int32(value: int) -> int:
    """Reproduce JavaScript's `x | 0` -- wrap to a signed 32-bit integer."""
    value &= _MASK
    return value - 0x100000000 if value >= 0x80000000 else value


def _imul(a: int, b: int) -> int:
    """Reproduce `Math.imul(a, b)`."""
    return _int32((a & _MASK) * (b & _MASK))


def _ushr(value: int, bits: int) -> int:
    """Reproduce the `>>>` unsigned right shift."""
    return (value & _MASK) >> bits


def mulberry32(seed: int) -> Callable[[], float]:
    """The exact PRNG used by the TypeScript generator."""
    state = _int32(seed)

    def rand() -> float:
        nonlocal state
        state = _int32(state + 0x6D2B79F5)
        t = _imul(state ^ _ushr(state, 15), 1 | state)
        t = _int32(_int32(t + _imul(t ^ _ushr(t, 7), 61 | t)) ^ t)
        return _ushr(t ^ _ushr(t, 14), 0) / 4294967296

    return rand


def _js_round(value: float) -> int:
    """`Math.round` semantics: halves go up. Python's `round` goes to even."""
    import math

    return math.floor(value + 0.5)


def _pick(rand: Callable[[], float], items: list) -> object:
    return items[int(rand() * len(items))]


def _pick_weighted(rand: Callable[[], float]) -> str:
    r = rand() * TOTAL_WEIGHT
    acc = 0
    for p in CUSTOMER_PROFILES:
        acc += p.weight
        if r <= acc:
            return p.name
    return CUSTOMER_PROFILES[0].name


def generate(today: date = TODAY, seed: int = SEED) -> tuple[Invoice, ...]:
    """Generate ~18 months of weekly invoice activity at Brocarga's scale.

    Roughly 175 orders and EUR 200k of revenue per week, margins driven by each
    customer's profile band, and payment behaviour driven by their late-payer
    bias -- which is what makes the segmentation matrix populate all four
    quadrants instead of clustering in one corner.
    """
    rand = mulberry32(seed)
    invoices: list[Invoice] = []
    inv_idx = 0

    for w in range(WEEKS - 1, -1, -1):
        week_anchor = today - timedelta(days=w * 7)

        orders = 160 + int(rand() * 31)             # 160..190 orders that week
        week_revenue_target = 180_000 + rand() * 40_000
        avg_per_order = week_revenue_target / orders

        for _ in range(orders):
            day_offset = int(rand() * 7)
            invoice_date = week_anchor - timedelta(days=day_offset)
            payment_terms = int(_pick(rand, PAYMENT_TERMS))
            due_date = invoice_date + timedelta(days=payment_terms)

            customer = _pick_weighted(rand)
            profile = PROFILE_BY_NAME[customer]
            broker = BROKERS[(len(customer) + CUSTOMERS.index(customer)) % len(BROKERS)]

            jitter = 0.4 + rand() * 1.6
            revenue = float(max(200, round(avg_per_order * jitter)))
            margin_pct = profile.margin_min + rand() * (profile.margin_max - profile.margin_min)
            margin = float(round(revenue * margin_pct))
            cost = revenue - margin
            financed = rand() < 0.55

            overdue_days = (today - due_date).days
            r_pay = rand()
            bias = profile.late_payer_bias

            if overdue_days < -5:
                early_paid_chance = 0.35 - bias * 0.3
                status = InvoiceStatus.PAID if r_pay < early_paid_chance else InvoiceStatus.OPEN
                outstanding = 0.0 if status is InvoiceStatus.PAID else revenue
            elif overdue_days < 0:
                paid_chance = 0.7 - bias * 0.5
                status = InvoiceStatus.PAID if r_pay < paid_chance else InvoiceStatus.OPEN
                outstanding = 0.0 if status is InvoiceStatus.PAID else revenue
            else:
                finqle_boost = 0.15 if financed else 0.0
                paid_chance = max(0.05, 0.85 - bias * 0.75 + finqle_boost)
                if r_pay < paid_chance:
                    status, outstanding = InvoiceStatus.PAID, 0.0
                elif r_pay < paid_chance + 0.06:
                    status = InvoiceStatus.PARTIALLY_PAID
                    outstanding = float(round(revenue * (0.2 + rand() * 0.6)))
                elif r_pay < paid_chance + 0.09:
                    status, outstanding = InvoiceStatus.DISPUTED, revenue
                else:
                    status, outstanding = InvoiceStatus.OVERDUE, revenue

            if status is InvoiceStatus.PAID:
                payment_status = PaymentStatus.PAID
            elif overdue_days > 0 and outstanding > 0:
                payment_status = PaymentStatus.OVERDUE
            else:
                payment_status = PaymentStatus.OPEN

            invoices.append(Invoice(
                invoice_number=f"BC-{100000 + inv_idx}",
                customer=customer,
                customer_id=f"C-{CUSTOMERS.index(customer) + 1:04d}",
                broker=broker,
                shipment_id=f"SHP-{500000 + inv_idx}",
                invoice_date=invoice_date,
                due_date=due_date,
                payment_terms=payment_terms,
                revenue=revenue,
                cost=cost,
                margin=margin,
                outstanding_amount=outstanding,
                invoice_amount=revenue,
                status=status,
                currency=Currency.EUR,
                financed_by_finqle=financed,
                financing_status=(
                    (FinancingStatus.SETTLED if status is InvoiceStatus.PAID
                     else FinancingStatus.ACTIVE) if financed else None
                ),
                financed_amount=float(round(revenue * 0.9)) if financed else None,
                financing_cost=float(round(revenue * 0.012)) if financed else None,
                payment_status=payment_status,
            ))
            inv_idx += 1

    return tuple(invoices)
