"""Payload builders -- one per dashboard tab.

Each builder takes the already-filtered rows and returns exactly the numbers one
tab renders, so a tab is one request and the browser does no arithmetic. Keeping
them here (rather than in the views) means a tab's contract can be tested with a
list of `Invoice` objects and no HTTP layer at all.

Ordering and truncation (`top 10`, `trailing 12 months`) live here too: they are
part of the contract the charts were designed against, not a display detail.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from . import aggregations as agg
from .types import Invoice

TOP_N = 10
INVOICE_TABLE_LIMIT = 500


def build_performance(rows: tuple[Invoice, ...], today: date) -> dict[str, Any]:
    """Performance tab: revenue/margin KPIs, trend, broker & customer rankings."""
    insights = agg.customer_insights(rows, today)
    by_broker = sorted(
        agg.group_by(rows, lambda r: r.broker, today),
        key=lambda g: g["revenue"],
        reverse=True,
    )
    by_customer = sorted(
        agg.group_by(rows, lambda r: r.customer, today),
        key=lambda g: g["revenue"],
        reverse=True,
    )[:TOP_N]

    # Customer x broker matrix behind the detail table.
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r.customer, r.broker)
        cur = pairs.get(key)
        if cur is None:
            cur = pairs[key] = {
                "customer": r.customer, "broker": r.broker,
                "revenue": 0.0, "margin": 0.0, "shipments": 0,
            }
        cur["revenue"] += r.revenue
        cur["margin"] += r.margin
        cur["shipments"] += 1

    return {
        "kpis": agg.aggregate(rows),
        "mom": agg.mom_growth(rows),
        "trend": agg.group_by_month(rows),
        "by_broker": by_broker,
        "by_customer": by_customer,
        "margin_ranking": sorted(insights, key=lambda c: c["margin"], reverse=True)[:TOP_N],
        "scatter": [
            {
                "x": round(c["revenue"]),
                "y": round(c["margin"]),
                "z": c["shipments"],
                "customer": c["customer"],
                "margin_pct": c["margin_pct"],
            }
            for c in insights
        ],
        "table": sorted(pairs.values(), key=lambda t: t["revenue"], reverse=True),
    }


def build_receivables(rows: tuple[Invoice, ...], today: date) -> dict[str, Any]:
    """Receivables & cashflow tab: exposure, aging, and the open-invoice table.

    The invoice table is capped at `INVOICE_TABLE_LIMIT` rows sorted by days
    overdue -- the collections worklist, not an export. Full extracts go through
    `/api/invoices/export/`.
    """
    by_customer = agg.group_by(rows, lambda r: r.customer, today)
    outstanding = sorted(
        (r for r in rows if r.outstanding_amount > 0),
        key=lambda r: r.days_overdue(today),
        reverse=True,
    )

    return {
        "kpis": agg.receivables_kpis(rows, today),
        "aging": agg.aging_breakdown(rows, today),
        "open_vs_overdue_by_month": agg.open_vs_overdue_by_month(rows, today),
        "open_by_customer": sorted(
            (g for g in by_customer if g["open"] > 0),
            key=lambda g: g["open"], reverse=True,
        )[:TOP_N],
        "overdue_by_customer": sorted(
            (g for g in by_customer if g["overdue"] > 0),
            key=lambda g: g["overdue"], reverse=True,
        )[:TOP_N],
        "finqle_split": agg.finqle_split(rows),
        "invoices": [
            {
                "invoice_number": r.invoice_number,
                "customer": r.customer,
                "broker": r.broker,
                "invoice_date": r.invoice_date,
                "due_date": r.due_date,
                "outstanding_amount": r.outstanding_amount,
                "status": r.status.value,
                "days_overdue": r.days_overdue(today),
                "financed_by_finqle": r.financed_by_finqle,
            }
            for r in outstanding[:INVOICE_TABLE_LIMIT]
        ],
        "invoices_truncated": len(outstanding) > INVOICE_TABLE_LIMIT,
        "invoices_total": len(outstanding),
    }


def build_customers(rows: tuple[Invoice, ...], today: date) -> dict[str, Any]:
    """Customer insights tab: segmentation matrix, ranking and collection actions.

    Benchmarks are the quadrant boundaries in the segmentation scatter: a
    customer above 12% margin and under 15 days late is in the healthy quadrant.
    """
    customers = agg.customer_insights(rows, today)
    total_revenue = sum(c["revenue"] for c in customers)

    return {
        "kpis": {
            "avg_margin_pct": (
                sum(c["margin_pct"] * c["revenue"] for c in customers) / total_revenue
                if total_revenue else 0.0
            ),
            "avg_days_overdue": (
                sum(c["avg_days_overdue"] for c in customers) / len(customers)
                if customers else 0.0
            ),
            "high_risk_count": sum(1 for c in customers if c["risk_score"] >= 60),
            "strategic_count": sum(
                1 for c in customers
                if c["margin_pct"] >= 0.15 and c["avg_days_overdue"] <= 10
            ),
            "customer_count": len(customers),
        },
        "benchmarks": {"margin_pct": 0.12, "days_overdue": 15},
        "segmentation": [
            {
                "x": round(c["margin_pct"] * 100, 2),
                "y": round(c["avg_days_overdue"]),
                "z": round(c["revenue"]),
                "customer": c["customer"],
                "risk_score": c["risk_score"],
            }
            for c in customers
        ],
        "ranked": sorted(customers, key=lambda c: c["revenue"], reverse=True),
        "actions": agg.collection_actions(customers),
    }
