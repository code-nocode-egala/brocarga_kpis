"""A stand-in dataset, in Bubble's own row shape.

Used when `BUBBLE_PROVIDER=sample`, so the backend starts, the dashboard fills
and the whole pipeline can be exercised without credentials or network — for a
first run, for a demo, and for the day the API token is rotated.

The rows are the same dicts `/api/1.1/obj/<type>` returns, not a parallel model:
they go through `Dataset` and `metrics` by exactly the path real rows take, so
what works here works against Bubble.

Deterministic by seed. The same seed always yields the same dashboard, which is
what makes "the numbers changed" a signal rather than noise.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

from . import schema as S

Row = dict[str, Any]

SEED = 20260101
MONTHS = 18
DEALS = 900

BROKERS = [
    "Klaas Boekestijn", "Bart Sardeman", "Marco Brozzu", "Sanne de Vries",
    "Tom Vermeulen", "Ilona Nowak", "Pieter Jansen", "Ayse Demir",
]
CUSTOMERS = [
    "Boekestijn Transport Service", "Dalessi Internationaal Transport",
    "Naviggo Group S.r.o.", "Myon Forwarding & Customs B.V.", "Kuehne Logistics NV",
    "Van Dijk Cold Chain", "Baltic Freight OU", "Iberia Cargo SL",
    "Rhein-Ruhr Spedition GmbH", "Nordic Haulage AB", "Alpine Trans AG",
    "Danube Logistics Kft", "Atlantic Reefer BV", "Meridian Bulk Ltd",
    "Vistula Transport Sp. z o.o.",
]

#: Weighted so most customers pay on time and a few are chronically late —
#: a uniform distribution would make the risk scores meaningless.
PAYMENT_TERMS = [14, 30, 30, 30, 45, 60, 7]


def _deal_status(rng: random.Random) -> str:
    """Mostly completed business, with a tail of the other Bubble statuses.

    The proportions mirror the real book (~90% `Release money`), so the
    deal-status filter has something to select and its default value visibly
    narrows the numbers.
    """
    roll = rng.random()
    if roll < 0.90:
        return S.DEAL_STATUS_LIVE
    if roll < 0.96:
        return "No deal"
    if roll < 0.98:
        return "Cancelled"
    return rng.choice(["Transport service", "Purchase", "Invoiced"])


def _finance_rule(rng: random.Random) -> str | None:
    roll = rng.random()
    if roll < 0.55:
        return S.DEAL_FINANCE_RULE_FINQLE
    if roll < 0.85:
        return S.DEAL_FINANCE_RULE_TI
    return None


def _bubble_id(rng: random.Random, when: datetime) -> str:
    """Bubble's id format: epoch millis, an "x", then a long random suffix."""
    return f"{int(when.timestamp() * 1000)}x{rng.randrange(10**17, 10**18)}"


def generate(seed: int = SEED, today: date | None = None) -> tuple[
    list[Row], list[Row], list[Row], list[Row]
]:
    rng = random.Random(seed)
    today = today or datetime.now(timezone.utc).date()
    start = datetime.combine(today - timedelta(days=MONTHS * 30), datetime.min.time(),
                             tzinfo=timezone.utc)

    users = [
        {S.USER_ID: _bubble_id(rng, start), S.USER_NAME: name,
         S.USER_LEVEL: "Broker" if i else "President"}
        for i, name in enumerate(BROKERS)
    ]
    relations = [
        {S.RELATION_ID: _bubble_id(rng, start), S.RELATION_NAME: name,
         S.RELATION_PAYMENT_TERM: str(rng.choice(PAYMENT_TERMS))}
        for name in CUSTOMERS
    ]

    # A few accounts carry most of the volume, as they do in the real book.
    weights = [1 / (i + 1) ** 0.8 for i in range(len(relations))]

    deals: list[Row] = []
    invoices: list[Row] = []
    span = (datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) - start).days

    for _ in range(DEALS):
        created = start + timedelta(days=rng.randrange(span), seconds=rng.randrange(86400))
        customer = rng.choices(relations, weights=weights)[0]
        revenue = round(rng.uniform(450, 6500), 2)
        margin = round(revenue * rng.uniform(0.02, 0.24), 2)

        deal: Row = {
            S.DEAL_ID: _bubble_id(rng, created),
            S.DEAL_DATE: created.isoformat().replace("+00:00", "Z"),
            S.DEAL_STATUS: _deal_status(rng),
            S.DEAL_REVENUE: revenue,
            S.DEAL_MARGIN: margin,
            S.DEAL_CUSTOMER: customer[S.RELATION_ID],
            # Coverage is decided per deal, so the sample decides it here too --
            # otherwise the sample provider reports zero Finqle exposure and
            # looks exactly like a broken field mapping against real data.
            # Three states, as in the real book: an explicit Finqle rule, an
            # explicit other rule, and the older deals that predate the field
            # and therefore read as Finqle by default.
            S.DEAL_FINANCE_RULE: _finance_rule(rng),
        }
        # One person often holds several roles on the same deal; occasionally a
        # role is unfilled. Both shapes occur in the real data and both have to
        # survive the aggregations.
        for role in S.BROKER_ROLE_FIELDS:
            if rng.random() > 0.08:
                deal[role] = rng.choice(users)[S.USER_ID]
        deals.append(deal)

        # Older deals are mostly settled; recent ones are mostly still open.
        age = (today - created.date()).days
        settled_odds = min(0.95, 0.25 + age / 240)
        issued = created + timedelta(days=rng.randrange(1, 21))
        invoices.append({
            S.INVOICE_ID: _bubble_id(rng, issued),
            S.INVOICE_DEAL: deal[S.DEAL_ID],
            S.INVOICE_DATE: issued.isoformat().replace("+00:00", "Z"),
            S.INVOICE_AMOUNT: revenue,
            S.INVOICE_FINQLE_STATUS: None if rng.random() < settled_odds else "OPEN",
            S.INVOICE_FINAL_FIELD: S.INVOICE_FINAL_VALUE,
            S.INVOICE_FINQLE_ID: (
                f"{rng.randrange(16**8):08x}-finqle" if rng.random() < 0.55 else None
            ),
        })

    return deals, users, invoices, relations
