"""The `/api/` endpoints.

`/api/dashboard/` is what the cockpit actually calls: it returns all three tab
payloads together, because they always describe the same filter set and a tab
should not be blank until its own round trip lands. The three per-tab endpoints
serve the same builders one at a time for anything that wants just one.

Each view does the same four things: get the snapshot, apply the filters, hand
the rows to `metrics`, and camelize the result. The payload builders live here
rather than in `metrics` so that a tab's contract — which fields, in what order,
truncated where — reads as one function next to the URL that serves it.

Ordering and truncation are part of the contract, not a display detail: the
React components are documented as forbidden to re-sort or re-slice what they
are given, so this is the only place those decisions are made.

Views are plain functions, not DRF. There is no database, no auth and no
serializer validation to justify the framework; `JsonResponse` and a
`camelize()` are the whole layer.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from django.conf import settings
from django.http import (FileResponse, Http404, HttpRequest, HttpResponse,
                         JsonResponse, StreamingHttpResponse)
from django.views.decorators.http import require_GET

from apps.bubble.exceptions import BubbleError

from . import metrics
from .dataset import Dataset, Row
from .filters import DEFAULT_DEAL_STATUS, Filters, apply_filters
from .params import parse_filters
from .serializers import camelize
from .source import get_dataset

logger = logging.getLogger(__name__)

TOP_N = metrics.TOP_N


def _json(payload: object, status: int = 200) -> JsonResponse:
    return JsonResponse(camelize(payload), status=status, json_dumps_params={"default": str})


@dataclass(frozen=True)
class Slice:
    """The deals a filter set selects, plus the aggregations built on them.

    Two of the three tab payloads want `customer_insights`, two want
    `revenue_by_customer`, and the receivables figures all walk the same
    invoice list. Serving the three tabs in one response must not pay for those
    twice, so the builders read them from here rather than calling `metrics`
    themselves. Each is computed on first use and only if some builder asks, so
    a single-tab request still does exactly that tab's work and no more.
    """

    ds: Dataset
    deals: tuple[Row, ...]

    @cached_property
    def insights(self) -> list[dict[str, Any]]:
        return metrics.customer_insights(self.deals, self.ds)

    @cached_property
    def by_customer(self) -> list[dict[str, Any]]:
        return metrics.revenue_by_customer(self.deals, self.ds)

    @cached_property
    def invoices(self) -> list[Row]:
        return self.ds.invoices_for(self.deals)

    @cached_property
    def outstanding(self) -> list[dict[str, Any]]:
        return metrics.outstanding_invoices(self.invoices, self.ds)


def _load(request: HttpRequest) -> tuple[Filters, Slice]:
    """Parsed filters and the slice of the snapshot they select.

    The dataset has to be loaded before the filters can be parsed: a period
    preset resolves against `dataset.as_of`, not against the server clock.
    """
    ds = get_dataset()
    f = parse_filters(request.GET, ds.as_of)
    return f, Slice(ds, apply_filters(ds, f))


def _bubble_error(exc: BubbleError) -> JsonResponse:
    """Bubble failures surface as themselves rather than as a 500.

    The distinction matters to whoever is paged: a 502 here means the upstream
    is unhappy, not that this service is broken.
    """
    logger.error("Bubble unavailable: %s", exc)
    return JsonResponse({"detail": exc.detail}, status=exc.http_status)


def _guard(view):
    """Turn any `BubbleError` raised inside a view into its HTTP response."""
    def wrapped(request: HttpRequest, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except BubbleError as exc:
            return _bubble_error(exc)
    wrapped.__name__ = view.__name__
    wrapped.__doc__ = view.__doc__
    return wrapped


# --------------------------------------------------------------------------
# Operational
# --------------------------------------------------------------------------

@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Liveness plus what the service is actually serving.

    Reports the live provider, so a deployment accidentally left on the sample
    data shows up as a wrong answer to a direct question rather than as a
    plausible-looking dashboard.
    """
    body = {
        "status": "ok",
        "provider": settings.BUBBLE["PROVIDER"],
        "debug": settings.DEBUG,
    }
    try:
        ds = get_dataset()
    except BubbleError as exc:
        body |= {"status": "degraded", "detail": exc.detail}
        return JsonResponse(body, status=exc.http_status)

    body |= {
        "as_of": ds.as_of.isoformat(),
        "fetched_at": ds.fetched_at,
        "deals": len(ds.deals),
        "invoices": len(ds.invoices),
        "customers": len(ds.relations),
        "brokers": len(ds.users),
    }
    return _json(body)


@require_GET
@_guard
def meta(request: HttpRequest) -> JsonResponse:
    """Filter-bar options and the dataset's reference date."""
    ds = get_dataset()
    return _json({
        "brokers": ds.broker_names,
        "customers": ds.customer_names,
        "statuses": ["Open", "Overdue", "Paid", "Partially Paid", "Disputed"],
        # Bubble's own deal statuses, and which one an unfiltered request means.
        "deal_statuses": ds.deal_statuses,
        "default_deal_status": DEFAULT_DEAL_STATUS,
        "as_of": ds.as_of.isoformat(),
        "periods": ["day", "week", "4weeks", "month", "quarter", "year", "all", "custom"],
        "source": ds.source,
        "fetched_at": ds.fetched_at,
    })


# --------------------------------------------------------------------------
# Dashboard tabs
# --------------------------------------------------------------------------
#
# One builder per tab, and one view per builder, plus `dashboard` which returns
# all three at once. The builders take a `Slice` rather than a request so that
# combined view can reuse them without filtering or aggregating three times;
# what it sends is the union of the three per-tab responses, field for field.


def build_performance(s: Slice) -> dict[str, Any]:
    """PerformancePayload: revenue and margin, by month, broker and customer."""
    trend = metrics.revenue_and_margin_trend(s.deals)

    return {
        "kpis": metrics.general_kpis(s.deals),
        "mom": metrics.mom_growth(trend),
        "trend": trend,
        "by_broker": metrics.revenue_by_broker(s.deals, s.ds),
        "by_customer": s.by_customer[:TOP_N],
        "margin_ranking": sorted(s.insights, key=lambda c: c["margin"], reverse=True)[:TOP_N],
        "scatter": metrics.profitability_scatter(s.insights),
        "table": metrics.performance_detail_table(s.deals, s.ds),
    }


def build_receivables(s: Slice) -> dict[str, Any]:
    """ReceivablesPayload: what is outstanding, how late, and who carries it."""
    limit = settings.DASHBOARD["TABLE_LIMIT"]

    return {
        "kpis": metrics.receivables_kpis(s.invoices, s.ds),
        "aging": metrics.aging_breakdown(s.invoices, s.ds),
        "open_vs_overdue_by_month": metrics.open_vs_overdue_by_month(s.invoices, s.ds),
        "open_by_customer": sorted(
            (g for g in s.by_customer if g["open"] > 0),
            key=lambda g: g["open"], reverse=True,
        )[:TOP_N],
        "overdue_by_customer": sorted(
            (g for g in s.by_customer if g["overdue"] > 0),
            key=lambda g: g["overdue"], reverse=True,
        )[:TOP_N],
        "finqle_split": metrics.finqle_split(s.invoices, s.ds),
        "invoices": s.outstanding[:limit],
        "invoices_truncated": len(s.outstanding) > limit,
        "invoices_total": len(s.outstanding),
    }


def build_customers(s: Slice) -> dict[str, Any]:
    """CustomersPayload: segmentation, ranking and the collections worklist."""
    insights = s.insights
    total_revenue = sum(c["revenue"] for c in insights)

    return {
        "kpis": {
            # Revenue-weighted: a 40% margin on one small shipment must not
            # outvote a 9% margin on the account that pays the rent.
            "avg_margin_pct": metrics.safe_div(
                sum(c["margin"] for c in insights), total_revenue
            ),
            "avg_days_overdue": metrics.safe_div(
                sum(c["avg_days_overdue"] for c in insights), len(insights)
            ),
            "high_risk_count": sum(1 for c in insights if c["risk_score"] >= 60),
            "strategic_count": sum(
                1 for c in insights
                if c["margin_pct"] >= 0.15 and c["avg_days_overdue"] <= 10
            ),
            "customer_count": len(insights),
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
            for c in insights if c["revenue"] > 0
        ],
        "ranked": sorted(insights, key=lambda c: c["revenue"], reverse=True),
        "actions": metrics.collection_actions(insights),
    }


@require_GET
@_guard
def dashboard(request: HttpRequest) -> JsonResponse:
    """All three tab payloads in one response, under one key each.

    The cockpit is a single filter bar over three tabs, so the three payloads
    always describe the same filter set and there is nothing to gain from
    asking for them separately: three requests meant three passes over the same
    filtered deals, and a tab that had never been opened had nothing on screen
    until its own round trip finished.

    The per-tab endpoints stay for callers that genuinely want one tab.
    """
    _f, s = _load(request)
    return _json({
        "performance": build_performance(s),
        "receivables": build_receivables(s),
        "customers": build_customers(s),
    })


@require_GET
@_guard
def performance(request: HttpRequest) -> JsonResponse:
    """The performance tab on its own."""
    return _json(build_performance(_load(request)[1]))


@require_GET
@_guard
def receivables(request: HttpRequest) -> JsonResponse:
    """The receivables tab on its own."""
    return _json(build_receivables(_load(request)[1]))


@require_GET
@_guard
def customers(request: HttpRequest) -> JsonResponse:
    """The customer-insights tab on its own."""
    return _json(build_customers(_load(request)[1]))


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

EXPORT_COLUMNS = (
    "invoice_number", "customer", "broker", "invoice_date", "due_date",
    "outstanding_amount", "status", "days_overdue", "financed_by_finqle",
)


@require_GET
@_guard
def export_transactions(request: HttpRequest) -> HttpResponse:
    """The full outstanding-invoice extract as CSV.

    Streamed rather than assembled: this is the one endpoint whose response is
    unbounded by a top-N, and buffering fifty thousand rows to measure a
    Content-Length would cost more than it is worth.
    """
    f, s = _load(request)
    rows = s.outstanding[: settings.DASHBOARD["EXPORT_LIMIT"]]

    class Echo:
        def write(self, value: str) -> str:
            return value

    writer = csv.writer(Echo())

    def stream():
        yield writer.writerow(EXPORT_COLUMNS)
        for row in rows:
            yield writer.writerow([row[c] for c in EXPORT_COLUMNS])

    filename = f"brocarga-transactions-{f.date_from}-{f.date_to}.csv"
    response = StreamingHttpResponse(stream(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# --------------------------------------------------------------------------
# The SPA
# --------------------------------------------------------------------------

@require_GET
def spa_index(request: HttpRequest) -> HttpResponse:
    """Serve the built React shell for any non-/api/ path.

    In development nothing reaches this: webpack-dev-server serves the app on
    :8080 and proxies /api here. It matters in production, and when the bundle
    has not been built the 404 says which command is missing rather than just
    failing.
    """
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise Http404(
            "The frontend bundle has not been built. Run `npm run build` in "
            "frontend/, or use `npm run dev` on :8080 during development."
        )
    return FileResponse(index.open("rb"), content_type="text/html")
