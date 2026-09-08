"""The aggregations, grown out of `scripts/play_bubble.py`.

Every function here is pure: it takes rows and a `Dataset` and returns plain
dicts. No Django, no network, no clock — `dataset.as_of` is the only "today",
so the same snapshot always produces the same numbers.

Keys are snake_case. `serializers.camelize` renames them to the camelCase in
`frontend/src/lib/api-types.ts`; that rename is the only place the two
spellings meet.

What changed on the way over from the script
--------------------------------------------
* The broker roles are the four that exist (`schema.BROKER_ROLE_FIELDS`).
* Payment terms are looked up by Relation id, not by Relation name, so invoices
  can actually age.
* An invoice is attributed to a broker through its Deal. `Deal_invoice` has no
  "created by" field, so the script's per-broker open/overdue was always zero.
* Open and overdue are amounts (`Amount_excl`), not invoice counts, because
  that is what `GroupRow.open` means to the React side.
* A deal counts as one shipment for a broker who holds several of its roles,
  while still carrying a role's share of the money for each role held.
* Divisions are guarded, and a deal pointing at a customer or broker missing
  from its table is skipped rather than raising `KeyError`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Sequence

from .schema import (
    BROKER_ROLE_FIELDS,
    DEAL_DATE,
    DEAL_ID,
    DEAL_MARGIN,
    DEAL_REVENUE,
    DEFAULT_PAYMENT_TERM_DAYS,
    INVOICE_DATE,
    INVOICE_DEAL,
    INVOICE_ID,
    ROLE_SHARE,
)

from .dataset import Dataset, Row, num, parse_date

TOP_N = 10
TREND_MONTHS = 12

MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

#: Days overdue at which the "how late" half of a risk score is maxed out.
RISK_DAYS_CEILING = 60.0
#: Margin below which a customer is scored as thin-margin.
THIN_MARGIN_PCT = 0.12
#: Overdue amount at which the "how much" half of a collection priority is maxed.
PRIORITY_BALANCE_CEILING = 25_000.0


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _clamp01(value: float) -> float:
    return 0.0 if value < 0 else 1.0 if value > 1 else value


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _month_label(key: str) -> str:
    """2026-07 -> "Jul 26", the short en-GB form the charts are laid out for."""
    year, month = key.split("-")
    return f"{MONTHS_SHORT[int(month) - 1]} {year[2:]}"


# --------------------------------------------------------------------------
# Headline KPIs
# --------------------------------------------------------------------------

def general_kpis(deals: Sequence[Row]) -> dict[str, float]:
    """
    PerformanceKpis for frontend Brocarga KPIs dashboard
    """
    gross = sum(num(deal.get(DEAL_REVENUE)) for deal in deals)
    margin = sum(num(deal.get(DEAL_MARGIN)) for deal in deals)
    shipments = len(deals)
    return {
        "gross_revenue": gross,
        "margin_revenue": margin,
        "margin_pct": safe_div(margin, gross),
        "shipments": shipments,
        "revenue_per_shipment": safe_div(gross, shipments),
        "margin_per_shipment": safe_div(margin, shipments),
    }

def revenue_and_margin_trend(deals: Iterable[Row]) -> list[dict[str, Any]]:
    """
    Revenue and margin per calendar month, oldest first, last 12 months.

    """
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "margin": 0.0})
    for deal in deals:
        when = parse_date(deal.get(DEAL_DATE))
        if when is None:
            continue
        bucket = monthly[_month_key(when)]
        bucket["revenue"] += num(deal.get(DEAL_REVENUE))
        bucket["margin"] += num(deal.get(DEAL_MARGIN))

    points = [
        {"month": key, "label": _month_label(key), "revenue": bucket["revenue"], "margin": bucket["margin"]}
        for key, bucket in sorted(monthly.items())
    ]
    return points[-TREND_MONTHS:]


def mom_growth(trend: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Month-over-month delta between the last two months present in the range."""
    if len(trend) < 2:
        return {"revenue": 0.0, "margin": 0.0}
    last, prev = trend[-1], trend[-2]
    return {
        "revenue": safe_div(last["revenue"] - prev["revenue"], prev["revenue"]),
        "margin": safe_div(last["margin"] - prev["margin"], prev["margin"]),
    }


# --------------------------------------------------------------------------
# Group rows (GroupRow in api-types.ts)
# --------------------------------------------------------------------------

def _blank_group(key: str) -> dict[str, Any]:
    return {"key": key, "revenue": 0.0, "margin": 0.0, "shipments": 0,
            "open": 0.0, "overdue": 0.0}


def revenue_by_broker(deals: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    """Revenue, margin, shipments and receivables rolled up per broker.
    """
    groups: dict[str, dict[str, Any]] = {}
    touched: dict[str, set[str]] = defaultdict(set)

    for deal in deals:
        deal_id = deal.get(DEAL_ID)
        revenue, margin = num(deal.get(DEAL_REVENUE)), num(deal.get(DEAL_MARGIN))
        invoices = ds.invoices_of_deal.get(deal_id, ())
        deal_open = sum(ds.amount(invoice) for invoice in invoices if ds.is_open(invoice))
        deal_overdue = sum(ds.amount(invoice) for invoice in invoices if ds.days_overdue(invoice) > 0)

        for user_id in ds.brokers_of(deal):
            name = ds.user_name.get(user_id)
            if name is None:
                # An external or deleted user: excluded from the User pull, so
                # their share is simply not attributed rather than invented.
                continue
            row = groups.setdefault(name, _blank_group(name))
            row["revenue"] += revenue * ROLE_SHARE
            row["margin"] += margin * ROLE_SHARE
            row["open"] += deal_open * ROLE_SHARE
            row["overdue"] += deal_overdue * ROLE_SHARE
            if deal_id:
                touched[name].add(deal_id)

    for name, deal_ids in touched.items():
        groups[name]["shipments"] = len(deal_ids)

    return sorted(groups.values(), key=lambda g: g["revenue"], reverse=True)


def revenue_by_customer(deals: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for deal in deals:
        name = ds.customer_name_of(deal)
        row = groups.setdefault(name, _blank_group(name))
        row["revenue"] += num(deal.get(DEAL_REVENUE))
        row["margin"] += num(deal.get(DEAL_MARGIN))
        row["shipments"] += 1
        for inv in ds.invoices_of_deal.get(deal.get(DEAL_ID), ()):
            if ds.is_open(inv):
                row["open"] += ds.amount(inv)
            if ds.days_overdue(inv) > 0:
                row["overdue"] += ds.amount(inv)

    return sorted(groups.values(), key=lambda g: g["revenue"], reverse=True)


# --------------------------------------------------------------------------
# Customer insights (CustomerInsight in api-types.ts)
# --------------------------------------------------------------------------

def customer_insights(deals: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    """Profitability, payment behaviour and a 0-100 risk score per customer."""
    acc: dict[str, dict[str, Any]] = {}

    for deal in deals:
        name = ds.customer_name_of(deal)
        cur = acc.get(name)
        if cur is None:
            cur = acc[name] = {
                "customer": name, "revenue": 0.0, "margin": 0.0, "shipments": 0,
                "open_amount": 0.0, "overdue_amount": 0.0,
                "_overdue_days": 0, "_overdue_count": 0,
                "_invoices": 0, "_finqle": 0,
            }
        cur["revenue"] += num(deal.get(DEAL_REVENUE))
        cur["margin"] += num(deal.get(DEAL_MARGIN))
        cur["shipments"] += 1

        # Constant across the deal's invoices, so it is decided once here;
        # `finqle_share` stays the share of *invoices* under covered deals.
        deal_is_finqle = ds.is_finqle(deal)

        for inv in ds.invoices_of_deal.get(deal.get(DEAL_ID), ()):
            cur["_invoices"] += 1
            if deal_is_finqle:
                cur["_finqle"] += 1
            if ds.is_open(inv):
                cur["open_amount"] += ds.amount(inv)
            late = ds.days_overdue(inv)
            if late > 0:
                cur["overdue_amount"] += ds.amount(inv)
                cur["_overdue_days"] += late
                cur["_overdue_count"] += 1

    total_revenue = sum(c["revenue"] for c in acc.values())

    out: list[dict[str, Any]] = []
    for c in acc.values():
        margin_pct = safe_div(c["margin"], c["revenue"])
        avg_days = safe_div(c["_overdue_days"], c["_overdue_count"])
        finqle_share = safe_div(c["_finqle"], c["_invoices"])
        out.append({
            "customer": c["customer"],
            "revenue": c["revenue"],
            "margin": c["margin"],
            "margin_pct": margin_pct,
            "open_amount": c["open_amount"],
            "overdue_amount": c["overdue_amount"],
            "avg_days_overdue": avg_days,
            "finqle_share": finqle_share,
            "shipments": c["shipments"],
            "risk_score": _risk_score(
                overdue_share=safe_div(c["overdue_amount"], c["open_amount"]),
                avg_days_overdue=avg_days,
                margin_pct=margin_pct,
                finqle_share=finqle_share,
            ),
            "rev_share": safe_div(c["revenue"], total_revenue),
        })
    return out


def _risk_score(
    *, overdue_share: float, avg_days_overdue: float, margin_pct: float, finqle_share: float
) -> float:
    """0-100. Overdue share 40, days overdue 30, thin margin 15, low Finqle 15.

    The weights are the contract documented on `CustomerInsight.riskScore`; the
    curves inside each term are the judgement calls. Days overdue saturate at
    `RISK_DAYS_CEILING` so a single ancient invoice cannot pin a customer at
    maximum risk forever, and the margin term only bites below
    `THIN_MARGIN_PCT` — a healthy margin does not reduce the risk of not being
    paid, it just stops adding to it.
    """
    thin = _clamp01((THIN_MARGIN_PCT - margin_pct) / THIN_MARGIN_PCT)
    return round(
        40 * _clamp01(overdue_share)
        + 30 * _clamp01(avg_days_overdue / RISK_DAYS_CEILING)
        + 15 * thin
        + 15 * _clamp01(1 - finqle_share),
        1,
    )


# --------------------------------------------------------------------------
# Profitability scatter + the customer x broker detail table
# --------------------------------------------------------------------------

def profitability_scatter(insights: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One bubble per trading customer: x revenue, y margin, size shipments.

    Customers with no revenue in the period are dropped. The Relation table
    holds ~700 counterparties and plotting the dormant ones would stack a few
    hundred bubbles on the origin and hide the chart's actual content.
    """
    return [
        {
            "x": round(c["revenue"]),
            "y": round(c["margin"]),
            "z": c["shipments"],
            "customer": c["customer"],
            "margin_pct": c["margin_pct"],
        }
        for c in insights
        if c["revenue"] > 0
    ]


def performance_detail_table(deals: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    pairs: dict[tuple[str, str], dict[str, Any]] = {}

    for deal in deals:
        customer = ds.customer_name_of(deal)
        revenue, margin = num(deal.get(DEAL_REVENUE)), num(deal.get(DEAL_MARGIN))
        for user_id in ds.brokers_of(deal):
            broker = ds.user_name.get(user_id)
            if broker is None:
                continue
            key = (customer, broker)
            row = pairs.get(key)
            if row is None:
                row = pairs[key] = {
                    "customer": customer, "broker": broker,
                    "revenue": 0.0, "margin": 0.0, "shipments": 0,
                }
            row["revenue"] += revenue * ROLE_SHARE
            row["margin"] += margin * ROLE_SHARE
            row["shipments"] += 1

    return sorted(pairs.values(), key=lambda r: r["revenue"], reverse=True)


# --------------------------------------------------------------------------
# Receivables
# --------------------------------------------------------------------------

AGING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("Current", 0, 0),
    ("1-7 days", 1, 7),
    ("8-30 days", 8, 30),
    ("31-60 days", 31, 60),
    ("61-90 days", 61, 90),
    ("90+ days", 91, None),
)


def receivables_kpis(invoices: Sequence[Row], ds: Dataset) -> dict[str, float]:
    open_invoices = [invoice for invoice in invoices if ds.is_open(invoice)]
    open_amount = sum(ds.amount(invoice) for invoice in open_invoices)

    overdue = [(invoice, ds.days_overdue(invoice)) for invoice in open_invoices]
    overdue = [(invoice, d) for invoice, d in overdue if d > 0]
    overdue_amount = sum(ds.amount(invoice) for invoice, _ in overdue)

    finqle_open = sum(
        ds.amount(invoice) for invoice in open_invoices if ds.is_finqle(ds.deal_of(invoice))
    )
    finqle_overdue = sum(
        ds.amount(invoice) for invoice, _ in overdue if ds.is_finqle(ds.deal_of(invoice))
    )

    return {
        "open_amount": open_amount,
        "overdue_amount": overdue_amount,
        "overdue_pct": safe_div(overdue_amount, open_amount),
        "open_count": len(open_invoices),
        "overdue_count": len(overdue),
        "avg_days_overdue": safe_div(sum(d for _, d in overdue), len(overdue)),
        "oldest": max((d for _, d in overdue), default=0),
        "finqle_open": finqle_open,
        "non_finqle_open": open_amount - finqle_open,
        "finqle_overdue": finqle_overdue,
        "non_finqle_overdue": overdue_amount - finqle_overdue,
        "brocarga_exposure": open_amount - finqle_open,
        "finqle_share_pct": safe_div(finqle_open, open_amount),
    }


def aging_breakdown(invoices: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    """Open balance split into the standard aging ladder."""
    buckets = {name: {"bucket": name, "amount": 0.0, "count": 0} for name, _, _ in AGING_BUCKETS}
    for inv in invoices:
        if not ds.is_open(inv):
            continue
        late = ds.days_overdue(inv)
        for name, low, high in AGING_BUCKETS:
            if late >= low and (high is None or late <= high):
                buckets[name]["amount"] += ds.amount(inv)
                buckets[name]["count"] += 1
                break
    return list(buckets.values())


def open_vs_overdue_by_month(invoices: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    """Open and overdue balance by the month the invoice was raised."""
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"open": 0.0, "overdue": 0.0})
    for inv in invoices:
        if not ds.is_open(inv):
            continue
        when = parse_date(inv.get(INVOICE_DATE))
        if when is None:
            continue
        bucket = monthly[_month_key(when)]
        bucket["open"] += ds.amount(inv)
        if ds.days_overdue(inv) > 0:
            bucket["overdue"] += ds.amount(inv)

    points = [
        {"month": k, "label": _month_label(k), "open": v["open"], "overdue": v["overdue"]}
        for k, v in sorted(monthly.items())
    ]
    return points[-TREND_MONTHS:]


def finqle_split(invoices: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    financed = sum(
        ds.amount(i) for i in invoices if ds.is_open(i) and ds.is_finqle(ds.deal_of(i))
    )
    direct = sum(
        ds.amount(i) for i in invoices if ds.is_open(i) and not ds.is_finqle(ds.deal_of(i))
    )
    return [{"name": "Finqle financed", "value": financed},
            {"name": "Brocarga direct", "value": direct}]


def outstanding_invoices(invoices: Sequence[Row], ds: Dataset) -> list[dict[str, Any]]:
    """The collections worklist: every open invoice, most overdue first.

    Deliberately narrower than the Bubble row — the caller truncates it, and
    `/api/transactions/export/` carries the full extract.
    """
    rows: list[dict[str, Any]] = []
    for inv in invoices:
        if not ds.is_open(inv):
            continue
        issued = parse_date(inv.get(INVOICE_DATE))
        if issued is None:
            continue
        deal_id = inv.get(INVOICE_DEAL)
        customer_id = ds.customer_of_deal.get(deal_id)
        term = ds.payment_term.get(customer_id, DEFAULT_PAYMENT_TERM_DAYS)
        late = ds.days_overdue(inv)
        rows.append({
            "invoice_number": inv.get(INVOICE_ID, ""),
            "customer": ds.customer_name.get(customer_id, "Unknown"),
            "broker": _primary_broker(deal_id, ds),
            "invoice_date": issued.isoformat(),
            "due_date": date.fromordinal(issued.toordinal() + term).isoformat(),
            "outstanding_amount": ds.amount(inv),
            "status": "Overdue" if late > 0 else "Open",
            "days_overdue": late,
            "financed_by_finqle": ds.is_finqle(ds.deal_by_id.get(deal_id, {})),
        })
    rows.sort(key=lambda r: r["days_overdue"], reverse=True)
    return rows


def _primary_broker(deal_id: str | None, ds: Dataset) -> str:
    """The one broker to show on an invoice row: whoever invoiced the deal.

    The worklist is a table of single values, so the four-way role split has to
    collapse. `$Invoiced_by` is the right collapse for a receivables view — it
    names the person the customer last heard from about this money.
    """
    deal = ds.deal_by_id.get(deal_id) if deal_id else None
    if not deal:
        return ""
    for role in ("$Invoiced_by", *BROKER_ROLE_FIELDS):
        name = ds.user_name.get(deal.get(role))
        if name:
            return name
    return ""


# --------------------------------------------------------------------------
# Collection actions
# --------------------------------------------------------------------------

_ACTIONS: tuple[tuple[float, str, str], ...] = (
    (75, "Consider Credit Hold", "destructive"),
    (55, "Escalate to Manager", "warning"),
    (35, "Call Customer", "warning"),
    (0, "Send Reminder", "default"),
)


def collection_actions(insights: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prioritised worklist over customers that owe something overdue.

    Priority weights are the contract on `CollectionAction.priority`: revenue at
    stake 30, days overdue 30, balance 25, unfinanced 15. Revenue at stake is
    the customer's share of total revenue — chasing the largest account is worth
    more attention than chasing the latest one.
    """
    total_revenue = sum(c["revenue"] for c in insights)
    out: list[dict[str, Any]] = []

    for c in insights:
        if c["overdue_amount"] <= 0:
            continue
        priority = round(
            30 * _clamp01(safe_div(c["revenue"], total_revenue) * 5)
            + 30 * _clamp01(c["avg_days_overdue"] / RISK_DAYS_CEILING)
            + 25 * _clamp01(c["overdue_amount"] / PRIORITY_BALANCE_CEILING)
            + 15 * _clamp01(1 - c["finqle_share"]),
            1,
        )
        action, tone = next((a, t) for threshold, a, t in _ACTIONS if priority >= threshold)
        out.append({
            "customer": c["customer"],
            "overdue_amount": c["overdue_amount"],
            "avg_days_overdue": c["avg_days_overdue"],
            "finqle_share": c["finqle_share"],
            "revenue": c["revenue"],
            "priority": priority,
            "action": action,
            "action_tone": tone,
        })

    out.sort(key=lambda a: a["priority"], reverse=True)
    return out
