#!/usr/bin/env python
"""Sandbox for `apps.bubble.client.BubbleClient` -- run it against data you own.

Two modes, one switch:

    MODE = "file"  ->  the client's HTTP session is swapped for a stub that
                       serves `DATA_FILE` back in real Bubble page envelopes.
                       Pagination, cursors and mapping all run for real; no
                       network, no credentials. Edit the JSON, re-run, look.
    MODE = "live"  ->  the same code path against your actual Bubble app,
                       using BASE_URL/API_TOKEN below (or the env vars).

Run from `backend/`:

    python scripts/play_bubble.py            # fetch, map, report
    python scripts/play_bubble.py --repl     # ...then drop into a shell with
                                             # `client`, `rows`, `invoices` bound

Needs Django and requests importable (`pip install django requests`).
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone


BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ==========================================================================
# EDIT ME
# ==========================================================================

# Read from the environment (backend/.env is loaded by config.settings, or
# export them yourself) so a private Bubble key does not live in a source file
# that is easy to share, paste or commit.
BASE_URL = os.environ.get("BUBBLE_BASE_URL", "")
API_TOKEN = os.environ.get("BUBBLE_API_TOKEN", "")
PAGE_SIZE = 100
MAX_ROWS = None                                  # None = everything

CONSTRAINTS = None                               # live mode only, e.g.
# CONSTRAINTS = [{"key": "Invoice Date", "constraint_type": "greater than",
#                 "value": "2025-01-01"}]

# Override Bubble field names without touching mappers.py, e.g.
# FIELD_MAP = {"revenue": "Turnover"}
FIELD_MAP: dict[str, str] = {}

BROKER_ROLE_FIELDS = ["$Sales_broker", "$Purchase_broker", "$Execution_broker", "$Account_manager"]

# -- the stub that stands in for Bubble in file mode ------------------------

class _Response:
    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class FakeBubbleSession:
    """Serves `rows` in Bubble's own page envelope, honouring cursor + limit."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs) -> _Response:
        params = kwargs.get("params") or kwargs.get("json") or {}
        cursor = int(params.get("cursor", 0))
        limit = int(params.get("limit", 100))
        page = self.rows[cursor:cursor + limit]
        remaining = max(len(self.rows) - (cursor + len(page)), 0)
        self.calls.append({"cursor": cursor, "limit": limit, "returned": len(page)})
        print(f"  -> {method} {url} cursor={cursor} limit={limit} "
              f"=> {len(page)} rows, {remaining} remaining")
        return _Response({"response": {
            "results": page, "cursor": cursor, "count": len(page), "remaining": remaining,
        }})


def calculate_gross_revenue(deal_list: list) -> float:
    return sum(
    item.get("Sales_price_total") or 0
    for item in deal_list
)

def calculate_margin_revenue(deal_list:list) -> float:
    return sum(
        item.get("Gross_margin") or 0
        for item in deal_list
    )

def get_number_of_shipments(deal_list:list) -> float:
    return len(deal_list)

def get_general_kpis(deal_list: list):
    gross_revenue = calculate_gross_revenue(deal_list)
    margin_revenue = calculate_margin_revenue(deal_list)
    shipments = len(deal_list)
    return   {
        "grossRevenue": gross_revenue,
        "marginRevenue": margin_revenue,
        "marginPct": margin_revenue/gross_revenue,
        "shipments": shipments,
        "revenuePerShipment": gross_revenue/shipments,
        "marginPerShipment": margin_revenue/shipments
    }

def get_revenue_and_margin_trend(deal_list: list):

    monthly = defaultdict(lambda: {
        "revenue": 0,
        "margin": 0
    })

    for item in deal_list:
        date = datetime.fromisoformat(item["Created Date"].replace("Z", "+00:00"))
        month = date.strftime("%Y-%m")

        monthly[month]["revenue"] += float(item.get("Sales_price_total") or 0)
        monthly[month]["margin"] += float(item.get("Gross_margin") or 0)

    return [
        {
            "month": month,
            "label": datetime.strptime(month, "%Y-%m").strftime("%b %y"),
            "revenue": values["revenue"],
            "margin": values["margin"]
        }
        for month, values in sorted(monthly.items())
    ]

def get_revenue_by_broker(
    deal_list: list,
    user_list: list,
    invoices_list: list,
    relations_list: list
):
    now = datetime.now(timezone.utc)

    # O(deals) — build Deal ID -> Shipper ID lookup once
    shipper_by_deal = {
        deal.get("_id"): deal.get("Shipper_id")
        for deal in deal_list
        if deal.get("_id")
    }

    # O(relations) — build Shipper Name -> Payment Term lookup once
    payment_term_by_shipper = {
        relation.get("Name"): int(relation.get("Payment_term") or 0)
        for relation in relations_list
        if relation.get("Name")
    }

    # O(users) — prepare result structure
    result_by_user = {
        user.get("_id"): {
            "key": user.get("Name"),
            "revenue": 0,
            "margin": 0,
            "shipments": 0,
            "open": 0,
            "overdue": 0
        }
        for user in user_list
    }

    for deal in deal_list:
        for broker_role in BROKER_ROLE_FIELDS:
            if deal.get(broker_role):
                result_by_user[deal.get(broker_role)]["revenue"] += deal.get("Sales_price_total") * 0.25
                result_by_user[deal.get(broker_role)]["margin"] += deal.get("Gross_margin") * 0.25
                result_by_user[deal.get(broker_role)]["shipments"] += 1

    # O(invoices)
    for invoice in invoices_list:
        user_id = invoice.get("Created By")

        # Ignore invoices belonging to users we're not returning
        if user_id not in result_by_user:
            continue

        status = invoice.get("FInqle_invoice_status")

        # Open / Submitted
        if status in {"OPEN", "SUBMITTED"}:
            result_by_user[user_id]["open"] += 1

        # Overdue
        if status in {"OPEN", "SUBMITTED"}:
            deal_id = invoice.get("Deal_id")
            shipper_id = shipper_by_deal.get(deal_id)

            payment_term = payment_term_by_shipper.get(shipper_id)

            if payment_term is not None:
                created_date = invoice.get("Created Date")

                if created_date:
                    created = datetime.fromisoformat(
                        created_date.replace("Z", "+00:00")
                    )

                    if (now - created).days > payment_term:
                        result_by_user[user_id]["overdue"] += 1

    return list(result_by_user.values())

def get_profitability_by_customer(
    deal_list: list,
    relations_list: list
):
    profitability_by_customer = {
        customer.get("_id"): {
            "x": 0,
            "y": 0,
            "z": 0,
            "customer": customer.get("Name"),
            "marginPct": 0
        }
        for customer in relations_list
    }

    for deal in deal_list:
        if deal.get("Shipper_id"):
            profitability_by_customer[deal.get("Shipper_id")]["y"] += deal.get("Sales_price_total")
            profitability_by_customer[deal.get("Shipper_id")]["x"] += deal.get("Gross_margin")
            profitability_by_customer[deal.get("Shipper_id")]["z"] += 1

    for customer in profitability_by_customer:
        if profitability_by_customer[customer]["y"]:
            profitability_by_customer[customer]["marginPct"] = profitability_by_customer[customer]["x"]/profitability_by_customer[customer]["y"]
        else:
            profitability_by_customer[customer]["marginPct"] = 0

    return profitability_by_customer



def get_revenue_by_customer(
    deal_list: list,
    invoices_list: list,
    relations_list: list
):
    now = datetime.now(timezone.utc)

    # O(deals) — build Deal ID -> Shipper ID lookup once
    shipper_by_deal = {
        deal.get("_id"): deal.get("Shipper_id")
        for deal in deal_list
        if deal.get("_id")
    }

    # O(relations) — build Shipper Name -> Payment Term lookup once
    payment_term_by_shipper = {
        relation.get("Name"): int(relation.get("Payment_term") or 0)
        for relation in relations_list
        if relation.get("Name")
    }

    # O(users) — prepare result structure
    result_by_customer = {
        customer.get("_id"): {
            "key": customer.get("Name"),
            "revenue": 0,
            "margin": 0,
            "shipments": 0,
            "open": 0,
            "overdue": 0
        }
        for customer in relations_list
    }


    for deal in deal_list:
        if deal.get("Shipper_id"):
            result_by_customer[deal.get("Shipper_id")]["revenue"] += deal.get("Sales_price_total")
            result_by_customer[deal.get("Shipper_id")]["margin"] += deal.get("Gross_margin")
            result_by_customer[deal.get("Shipper_id")]["shipments"] += 1

    # O(invoices)
    for invoice in invoices_list:
        deal_id = invoice.get("Deal_id")
        customer_id = shipper_by_deal.get(deal_id)

        if customer_id not in result_by_customer:
            continue

        status = invoice.get("FInqle_invoice_status")

        # Open / Submitted
        if status in {"OPEN", "SUBMITTED"}:
            result_by_customer[customer_id]["open"] += 1

        # Overdue
        if status in {"OPEN", "SUBMITTED"}:
            deal_id = invoice.get("Deal_id")
            shipper_id = shipper_by_deal.get(deal_id)

            payment_term = payment_term_by_shipper.get(shipper_id)

            if payment_term is not None:
                created_date = invoice.get("Created Date")

                if created_date:
                    created = datetime.fromisoformat(
                        created_date.replace("Z", "+00:00")
                    )

                    if (now - created).days > payment_term:
                        result_by_customer[customer_id]["overdue"] += 1

    return list(result_by_customer.values())

def performance_detail_table(deal_list: list, users_list: list, relations_list: list):
    profitability_table = []
    for customer in relations_list:
        for user in users_list:
            profitability_table.append({
                "customer": customer.get("Name"),
                "broker": "",
                "revenue": 0,
                "margin": 0,
                "shipments": 0
            })

    return

def main() -> None:
    from apps.bubble.client import BubbleClient

    client = BubbleClient(BASE_URL, API_TOKEN, 1000, 5)
    deals = list(client.list_objects(
        "Deal",
        constraints=[{"key": "Status", "constraint_type": "equals", "value": "Release money"}],
        page_size=PAGE_SIZE,
        max_rows=15000,
    ))
    users = list(client.list_objects(
        "User",
        constraints=[{"key": "User level", "constraint_type": "not equal", "value": "External"}],
        page_size=PAGE_SIZE,
        max_rows=10000,
    ))
    invoices = list(client.list_objects(
        "Deal_invoice",
        constraints=[{"key": "Status_final_wrong", "constraint_type": "equals", "value": "Final"}],
        page_size=PAGE_SIZE,
        max_rows=10000,
    ))
    relations = list(client.list_objects(
        "Relation",
        constraints=[],
        page_size=PAGE_SIZE,
        max_rows=10000,
    ))
    #print(get_revenue_by_broker(deals, users, invoices, relations))
    #print(get_revenue_and_margin_trend(deals))
    #print(get_revenue_by_customer(deals, invoices, relations))
    #print(get_general_kpis(deals))
    print(get_profitability_by_customer(deals, relations))



if __name__ == "__main__":
    main()
