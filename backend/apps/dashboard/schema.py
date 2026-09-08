# -- data types -------------------------------------------------------------

DEAL = "Deal"
USER = "User"
INVOICE = "Deal_invoice"
RELATION = "Relation"

# -- Deal -------------------------------------------------------------------

DEAL_ID = "_id"
DEAL_DATE = "Created Date"
DEAL_REVENUE = "Sales_price_total"
DEAL_MARGIN = "Gross_margin"
DEAL_CUSTOMER = "Shipper_id"
DEAL_STATUS = "Status"
DEAL_FINANCE_RULE = "finance_rule"

#: Value of DEAL_FINANCE_RULE meaning Finqle carries the receivable. Coverage
#: is agreed per deal, so it is the deal that answers "is this financed?" --
#: the invoice only inherits the answer through its deal.
DEAL_FINANCE_RULE_FINQLE = "Finqle_covers"

#: The other rule seen in the data: Brocarga carries the receivable itself.
#: Only an explicit value like this one counts as "not Finqle" -- see
#: `Dataset.is_finqle` for why a *missing* rule does not.
DEAL_FINANCE_RULE_TI = "TI_covers"


#: The status a deal reaches once the money is released -- the only one that
#: represents completed, billable business. This is the *default* value of the
#: deal-status filter rather than a constraint on the pull: every status is
#: fetched so the filter bar can select the others.
DEAL_STATUS_LIVE = "Release money"


BROKER_ROLE_FIELDS: tuple[str, ...] = (
    "$Created_by",
    "$Confirmed_by",
    "$Invoiced_by",
    "$Account_Manager",
)

ROLE_SHARE = 0.25

USER_ID = "_id"
USER_NAME = "Name"
USER_LEVEL = "User level"

USER_LEVEL_EXTERNAL = "External"

INVOICE_ID = "_id"
INVOICE_DEAL = "Deal_id"
INVOICE_DATE = "Created Date"
INVOICE_AMOUNT = "Amount_excl"
INVOICE_FINQLE_STATUS = "FInqle_invoice_status"  # sic - the capital I is Bubble's
INVOICE_FINQLE_ID = "Factoring_invoice_id"

INVOICE_OPEN_STATUSES = frozenset({"OPEN", "SUBMITTED"})

INVOICE_FINAL_FIELD = "Status_final_wrong"
INVOICE_FINAL_VALUE = "Final"

RELATION_ID = "_id"
RELATION_NAME = "Name"
RELATION_PAYMENT_TERM = "Payment_term"

DEFAULT_PAYMENT_TERM_DAYS = 30
