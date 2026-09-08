"""Pure aggregation functions -- the analytical core of the cockpit.

Ported from `frontend/src/lib/dashboard-data.ts` plus the per-tab `useMemo`
blocks in `src/components/dashboard/*Tab.tsx`. Moving them here is the point of
the backend: the browser stops receiving ~13k invoice rows and receives a few KB
of pre-aggregated numbers instead.

Every function is total (empty input -> zeros, never a division by zero) and
takes `today` explicitly so overdue maths is deterministic and testable.

Keys are snake_case here; `apps.api.serializers` renames them to the camelCase
the React components already expect.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Callable, Iterable

from .types import Invoice

MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _month_label(key: str) -> str:
    """Turn 2026-07 into "Jul 26" -- the en-GB short format used in the charts."""
    year, month = key.split("-")
    return f"{MONTHS_SHORT[int(month) - 1]} {year[2:]}"


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

def aggregate(rows: Iterable[Invoice]) -> dict[str, float]:
    """Headline performance KPIs."""
    rows = tuple(rows)
    gross = sum(r.revenue for r in rows)
    margin = sum(r.margin for r in rows)
    shipments = len(rows)
    return {
        "gross_revenue": gross,
        "margin_revenue": margin,
        "margin_pct": _safe_div(margin, gross),
        "shipments": shipments,
        "revenue_per_shipment": _safe_div(gross, shipments),
        "margin_per_shipment": _safe_div(margin, shipments),
    }


def group_by_month(rows: Iterable[Invoice]) -> list[dict[str, Any]]:
    """Revenue/margin per calendar month of invoice date, chronological."""
    buckets: dict[str, dict[str, float]] = {}
    for r in rows:
        key = _month_key(r.invoice_date)
        cur = buckets.setdefault(key, {"revenue": 0.0, "margin": 0.0})
        cur["revenue"] += r.revenue
        cur["margin"] += r.margin
    return [
        {"month": k, "label": _month_label(k), "revenue": v["revenue"], "margin": v["margin"]}
        for k, v in sorted(buckets.items())
    ]


def mom_growth(rows: Iterable[Invoice]) -> dict[str, float]:
    """Month-over-month delta between the last two months present in the range."""
    months = group_by_month(rows)
    if len(months) < 2:
        return {"revenue": 0.0, "margin": 0.0}
    last, prev = months[-1], months[-2]
    return {
        "revenue": _safe_div(last["revenue"] - prev["revenue"], prev["revenue"]),
        "margin": _safe_div(last["margin"] - prev["margin"], prev["margin"]),
    }


def group_by(
    rows: Iterable[Invoice],
    key_fn: Callable[[Invoice], str],
    today: date,
) -> list[dict[str, Any]]:
    """Revenue / margin / shipments / open / overdue rolled up by an arbitrary key."""
    buckets: dict[str, dict[str, Any]] = {}
    for r in rows:
        k = key_fn(r)
        cur = buckets.get(k)
        if cur is None:
            cur = buckets[k] = {
                "key": k, "revenue": 0.0, "margin": 0.0,
                "shipments": 0, "open": 0.0, "overdue": 0.0,
            }
        cur["revenue"] += r.revenue
        cur["margin"] += r.margin
        cur["shipments"] += 1
        cur["open"] += r.outstanding_amount
        if r.is_overdue(today):
            cur["overdue"] += r.outstanding_amount
    return list(buckets.values())


# --------------------------------------------------------------------------
# Receivables
# --------------------------------------------------------------------------

AGING_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("Current", -math.inf, 0),
    ("1-7 days", 1, 7),
    ("8-30 days", 8, 30),
    ("31-60 days", 31, 60),
    ("61-90 days", 61, 90),
    ("90+ days", 91, math.inf),
)


def receivables_kpis(rows: Iterable[Invoice], today: date) -> dict[str, float]:
    """Open/overdue exposure, split by who carries the risk.

    Finqle finances part of the book; on those invoices Finqle carries the
    receivable, so Brocarga's *direct* exposure is the non-financed open amount.
    """
    outstanding = [r for r in rows if r.outstanding_amount > 0]
    overdue = [r for r in outstanding if r.is_overdue(today)]

    open_amount = sum(r.outstanding_amount for r in outstanding)
    overdue_amount = sum(r.outstanding_amount for r in overdue)
    finqle_open = sum(r.outstanding_amount for r in outstanding if r.financed_by_finqle)
    finqle_overdue = sum(r.outstanding_amount for r in overdue if r.financed_by_finqle)
    non_finqle_open = open_amount - finqle_open

    return {
        "open_amount": open_amount,
        "overdue_amount": overdue_amount,
        "overdue_pct": _safe_div(overdue_amount, open_amount),
        "open_count": len(outstanding),
        "overdue_count": len(overdue),
        "avg_days_overdue": _safe_div(
            sum(r.days_overdue(today) for r in overdue), len(overdue)
        ),
        "oldest": max((r.days_overdue(today) for r in overdue), default=0),
        "finqle_open": finqle_open,
        "non_finqle_open": non_finqle_open,
        "finqle_overdue": finqle_overdue,
        "non_finqle_overdue": overdue_amount - finqle_overdue,
        "brocarga_exposure": non_finqle_open,
        "finqle_share_pct": _safe_div(finqle_open, open_amount),
    }


def aging_breakdown(rows: Iterable[Invoice], today: date) -> list[dict[str, Any]]:
    """Outstanding amount per aging bucket. Current = outstanding, not yet due."""
    outstanding = [r for r in rows if r.outstanding_amount > 0]
    out: list[dict[str, Any]] = []
    for name, low, high in AGING_BUCKETS:
        if name == "Current":
            hits = [r for r in outstanding if not r.is_overdue(today)]
        else:
            hits = [r for r in outstanding if low <= r.days_overdue(today) <= high]
        out.append({
            "bucket": name,
            "amount": sum(r.outstanding_amount for r in hits),
            "count": len(hits),
        })
    return out


def open_vs_overdue_by_month(
    rows: Iterable[Invoice], today: date, months: int = 12
) -> list[dict[str, Any]]:
    """Outstanding split open vs overdue, per month, trailing `months`."""
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"open": 0.0, "overdue": 0.0})
    for r in rows:
        if r.outstanding_amount <= 0:
            continue
        cur = buckets[_month_key(r.invoice_date)]
        if r.is_overdue(today):
            cur["overdue"] += r.outstanding_amount
        else:
            cur["open"] += r.outstanding_amount
    ordered = sorted(buckets.items())[-months:]
    return [
        {"month": k, "label": _month_label(k), "open": v["open"], "overdue": v["overdue"]}
        for k, v in ordered
    ]


def finqle_split(rows: Iterable[Invoice]) -> list[dict[str, Any]]:
    """Open receivable split between Finqle-financed and self-carried."""
    finqle = non_finqle = 0.0
    for r in rows:
        if r.outstanding_amount <= 0:
            continue
        if r.financed_by_finqle:
            finqle += r.outstanding_amount
        else:
            non_finqle += r.outstanding_amount
    return [
        {"name": "Finqle-financed", "value": finqle},
        {"name": "Non-Finqle", "value": non_finqle},
    ]


# --------------------------------------------------------------------------
# Customer insights
# --------------------------------------------------------------------------

def customer_insights(rows: Iterable[Invoice], today: date) -> list[dict[str, Any]]:
    """Per-customer profitability, payment behaviour and a 0-100 risk score.

    Risk weighting (unchanged from the frontend): overdue share of the open
    balance 40, how long it has been overdue 30, thin margin 15, and how little
    of the customer's volume Finqle absorbs 15.
    """
    rows = tuple(rows)
    grouped = {g["key"]: g for g in group_by(rows, lambda r: r.customer, today)}

    per_customer: dict[str, list[Invoice]] = defaultdict(list)
    for r in rows:
        per_customer[r.customer].append(r)

    out: list[dict[str, Any]] = []
    for name, g in grouped.items():
        cust_rows = per_customer[name]
        overdue_rows = [r for r in cust_rows if r.is_overdue(today)]
        avg_days_overdue = _safe_div(
            sum(r.days_overdue(today) for r in overdue_rows), len(overdue_rows)
        )
        finqle_share = _safe_div(
            sum(1 for r in cust_rows if r.financed_by_finqle), len(cust_rows)
        )
        margin_pct = _safe_div(g["margin"], g["revenue"])

        risk = min(100, round(
            _safe_div(g["overdue"], max(1.0, g["open"] + 1)) * 40
            + min(avg_days_overdue, 90) / 90 * 30
            + (1 - min(margin_pct * 5, 1)) * 15
            + (1 - finqle_share) * 15
        ))

        out.append({
            "customer": name,
            "revenue": g["revenue"],
            "margin": g["margin"],
            "margin_pct": margin_pct,
            "open_amount": g["open"],
            "overdue_amount": g["overdue"],
            "avg_days_overdue": avg_days_overdue,
            "finqle_share": finqle_share,
            "shipments": g["shipments"],
            "risk_score": risk,
            "rev_share": g["revenue"],
        })
    return out


# (min avg days overdue, min overdue amount, label, tone) -- first match wins.
ACTION_LADDER: tuple[tuple[float, float, str, str], ...] = (
    (60, 50_000, "Consider Credit Hold", "destructive"),
    (45, 0, "Escalate to Management", "destructive"),
    (30, 0, "Review Credit Exposure", "warning"),
    (14, 0, "Escalate to Broker", "warning"),
)


def collection_actions(customers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank customers with overdue balances into a prioritised worklist.

    Priority 0-100: revenue at stake 30, how overdue 30, size of the overdue
    balance 25, unfinanced share 15. The action ladder escalates from a reminder
    to a credit hold.
    """
    out: list[dict[str, Any]] = []
    for c in customers:
        if c["overdue_amount"] <= 0:
            continue
        priority = round(
            min(c["revenue"] / 200_000, 1) * 30
            + min(c["avg_days_overdue"] / 90, 1) * 30
            + min(c["overdue_amount"] / 100_000, 1) * 25
            + (1 - c["finqle_share"]) * 15
        )
        action, action_tone = "Send Reminder", "default"
        for min_days, min_amount, label, tone in ACTION_LADDER:
            if c["avg_days_overdue"] > min_days and c["overdue_amount"] > min_amount:
                action, action_tone = label, tone
                break

        out.append({
            "customer": c["customer"],
            "overdue_amount": c["overdue_amount"],
            "avg_days_overdue": c["avg_days_overdue"],
            "finqle_share": c["finqle_share"],
            "revenue": c["revenue"],
            "priority": priority,
            "action": action,
            "action_tone": action_tone,
        })
    out.sort(key=lambda a: a["priority"], reverse=True)
    return out
