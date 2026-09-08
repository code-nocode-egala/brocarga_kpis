from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable

from . import schema as S

Row = dict[str, Any]


def parse_dt(value: Any) -> datetime | None:
    """Parse a Bubble ISO timestamp ("2022-06-30T20:40:00.072Z") as UTC-aware."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_date(value: Any) -> date | None:
    parsed = parse_dt(value)
    return parsed.date() if parsed else None


def num(value: Any) -> float:
    """Bubble sends numbers, numeric strings and nulls for the same field."""
    if value is None or value is True or value is False:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class Dataset:
    """Everything one dashboard request reads, already joined.

    `as_of` is the reference date for every overdue calculation. It is carried
    on the snapshot rather than read from the clock inside the aggregations so
    that a cached snapshot cannot change meaning as midnight passes mid-session.
    """

    deals: tuple[Row, ...]
    users: tuple[Row, ...]
    invoices: tuple[Row, ...]
    relations: tuple[Row, ...]
    as_of: date
    fetched_at: str
    source: str

    # -- lookups, all built in __post_init__ -----------------------------
    user_name: dict[str, str] = field(default_factory=dict)
    customer_name: dict[str, str] = field(default_factory=dict)
    payment_term: dict[str, int] = field(default_factory=dict)
    deal_by_id: dict[str, Row] = field(default_factory=dict)
    customer_of_deal: dict[str, str] = field(default_factory=dict)
    invoices_of_deal: dict[str, list[Row]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for user in self.users:
            uid = user.get(S.USER_ID)
            if uid:
                self.user_name[uid] = (user.get(S.USER_NAME) or "").strip() or uid

        for rel in self.relations:
            rid = rel.get(S.RELATION_ID)
            if not rid:
                continue
            self.customer_name[rid] = (rel.get(S.RELATION_NAME) or "").strip() or rid
            term = rel.get(S.RELATION_PAYMENT_TERM)
            # Payment_term comes back as a string ("30") often enough to matter.
            self.payment_term[rid] = int(num(term)) if term not in (None, "") else (
                S.DEFAULT_PAYMENT_TERM_DAYS
            )

        for deal in self.deals:
            did = deal.get(S.DEAL_ID)
            if not did:
                continue
            self.deal_by_id[did] = deal
            if deal.get(S.DEAL_CUSTOMER):
                self.customer_of_deal[did] = deal[S.DEAL_CUSTOMER]

        for inv in self.invoices:
            deal_id = inv.get(S.INVOICE_DEAL)
            
            if deal_id:
                self.invoices_of_deal.setdefault(deal_id, []).append(inv)

    # -- filter-bar options ----------------------------------------------

    @property
    def broker_names(self) -> list[str]:
        return sorted(set(self.user_name.values()))

    @property
    def deal_statuses(self) -> list[str]:
        """Every Bubble deal status present in the snapshot, sorted.

        Read off the rows rather than hard-coded: Bubble's status list is an
        option set someone can extend, and a filter offering a value the data
        does not have -- or missing one it does -- is worse than a list that
        simply describes what is there.
        """
        return sorted({
            status for deal in self.deals
            if (status := (deal.get(S.DEAL_STATUS) or "").strip())
        })

    @property
    def customer_names(self) -> list[str]:
        """Only customers that actually have a deal.

        The Relation table holds every counterparty ever created (hauliers,
        dormant leads); listing all of them would bury the ~200 the filter bar
        is useful for in 700 entries.
        """
        seen = {
            self.customer_of_deal[d[S.DEAL_ID]]
            for d in self.deals
            if d.get(S.DEAL_ID) in self.customer_of_deal
        }
        return sorted({self.customer_name[c] for c in seen if c in self.customer_name})

    # -- joins ------------------------------------------------------------

    def customer_name_of(self, deal: Row) -> str:
        cid = deal.get(S.DEAL_CUSTOMER)
        return self.customer_name.get(cid, "Unknown") if cid else "Unknown"

    def brokers_of(self, deal: Row) -> list[str]:
        """The user ids credited on a deal, one per filled role.

        A role may be empty, and one person often holds several roles on the
        same deal; duplicates are kept because each role carries its own share.
        """
        return [deal[f] for f in S.BROKER_ROLE_FIELDS if deal.get(f)]

    def invoices_for(self, deals: Iterable[Row]) -> list[Row]:
        out: list[Row] = []
        for deal in deals:
            out.extend(self.invoices_of_deal.get(deal.get(S.DEAL_ID), ()))
        return out

    # -- invoice state ----------------------------------------------------

    def is_open(self, invoice: Row) -> bool:
        status = invoice.get(S.INVOICE_FINQLE_STATUS)
        return bool(status) and str(status).upper() in S.INVOICE_OPEN_STATUSES

    def days_overdue(self, invoice: Row) -> int:
        """Days past the customer's payment term, 0 if settled or within term.

        Bubble has no due date on the invoice, so it is derived: invoice date
        plus the payment term of the Relation the invoice's Deal belongs to.
        """
        if not self.is_open(invoice):
            return 0
        issued = parse_date(invoice.get(S.INVOICE_DATE))
        if issued is None:
            return 0
        customer_id = self.customer_of_deal.get(invoice.get(S.INVOICE_DEAL))
        term = self.payment_term.get(customer_id, S.DEFAULT_PAYMENT_TERM_DAYS)
        overdue = (self.as_of - issued).days - term
        return overdue if overdue > 0 else 0

    def amount(self, invoice: Row) -> float:
        return num(invoice.get(S.INVOICE_AMOUNT))

    def deal_of(self, invoice: Row) -> Row:
        """The deal an invoice belongs to, or an empty row if it has none.

        Finqle coverage lives on the deal, so every invoice-level question about
        financing has to make this hop first. An empty row rather than `None`
        keeps the callers free of a null check: an invoice whose deal fell
        outside the snapshot simply is not covered.
        """
        return self.deal_by_id.get(invoice.get(S.INVOICE_DEAL), {})

    def is_finqle(self, deal: Row) -> bool:
        """Whether Finqle carries this deal's receivable.

        Takes a deal, not an invoice: the arrangement is agreed on the deal and
        every invoice under it inherits the same answer. Use `deal_of` to get
        here from an invoice.

        A *missing* rule reads as Finqle. `finance_rule` only started being
        recorded partway through the book, so every deal older than the field
        has no value at all -- and those were financed. Treating the gap as
        "not financed" would have understated Finqle coverage by the entire
        history rather than leaving it merely unknown. Only an explicit other
        rule (TI_covers) is a no.

        An empty row is not a deal at all -- `deal_of` returns one for an
        invoice whose deal is outside the snapshot -- and answers False, so a
        missing join never counts as coverage.
        """
        if not deal:
            return False
        rule = deal.get(S.DEAL_FINANCE_RULE)
        return not rule or rule == S.DEAL_FINANCE_RULE_FINQLE
