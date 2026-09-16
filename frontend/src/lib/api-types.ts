/**
 * The wire contract between Django and this app.
 *
 * Every shape here mirrors one payload builder in the backend:
 *
 *   GET /api/meta/                     -> MetaResponse
 *   GET /api/dashboard/                -> DashboardPayload     (dashboard)
 *   GET /api/dashboard/performance/    -> PerformancePayload   (build_performance)
 *   GET /api/dashboard/receivables/    -> ReceivablesPayload   (build_receivables)
 *   GET /api/dashboard/customers/      -> CustomersPayload     (build_customers)
 *   GET /api/dashboard/portfolio/      -> PortfolioPayload     (build_portfolio)
 *   GET /api/transactions/export/      -> text/csv
 *
 * `/api/dashboard/` is the one this app calls: the three tabs share a filter
 * bar, so they arrive together and switching tabs never waits on the network.
 * The per-tab endpoints are the same payloads served one at a time.
 *
 * The backend computes in snake_case and its serializers rename to the camelCase
 * below — that rename is the only place the two spellings meet. The browser does
 * no aggregation: it receives finished numbers and renders them. Ordering and
 * truncation (top 10, trailing 12 months, the 500-row collections worklist) are
 * part of the contract and already applied server side, so the components must
 * not re-sort or re-slice what they are given.
 *
 * Every payload has an EMPTY_* counterpart at the bottom of this file. Those are
 * what the tabs render before the first response lands, and what they fall back
 * to when the API is unreachable — the dashboard stays laid out and readable at
 * zero rather than blanking out.
 */

export type PeriodPreset =
  | "day"
  | "week"
  | "4weeks"
  | "month"
  | "quarter"
  | "year"
  | "all"
  | "custom";

/**
 * The deal status an unfiltered request selects. Mirrors
 * `DEFAULT_DEAL_STATUS` in `apps/dashboard/filters.py`.
 *
 * The snapshot carries every Bubble status, but the dashboard is about
 * completed business, so leaving the filter alone must not start counting
 * cancelled deals as revenue. Used only until /api/meta/ confirms it.
 */
export const DEFAULT_DEAL_STATUS = "Release money";

export type InvoiceStatus = "Open" | "Paid" | "Partially Paid" | "Overdue" | "Disputed";

export type Currency = "EUR" | "USD" | "GBP";

/** Tone the backend attaches to a recommended action; maps to a badge style. */
export type ActionTone = "default" | "warning" | "destructive";

// ---------------------------------------------------------------------------
// Filter-bar options — GET /api/meta/
// ---------------------------------------------------------------------------

export interface MetaResponse {
  /** Broker names present in the dataset, sorted. */
  brokers: string[];
  /** Customer names present in the dataset, sorted. */
  customers: string[];
  /** Selectable *invoice* status values (excluding the "all" sentinel). */
  statuses: InvoiceStatus[];
  /**
   * Bubble's own `Status` on the deal, as present in the snapshot
   * ("Release money", "Cancelled", "No deal", ...). Read off the rows, so it
   * describes the data rather than a hard-coded option set.
   */
  dealStatuses: string[];
  /** Which of those a request with no `dealStatus` parameter means. */
  defaultDealStatus: string;
  /**
   * Reference date every overdue calculation is anchored to (Dataset.as_of).
   * Not "today in the browser" — the dataset decides what today means, so the
   * date pickers clamp to this instead of to the client clock.
   */
  asOf: string;
  /** Period presets the backend knows how to resolve. */
  periods: PeriodPreset[];
  /** Where the rows came from ("bubble", "mock", ...). */
  source: string;
  /** When the upstream fetch happened; null if never fetched. */
  fetchedAt: string | null;
}

// ---------------------------------------------------------------------------
// Shared row shapes
// ---------------------------------------------------------------------------

/** One bucket from group_by — a broker, a customer, whatever was keyed on. */
export interface GroupRow {
  key: string;
  revenue: number;
  margin: number;
  shipments: number;
  /** Outstanding amount, i.e. still unpaid. */
  open: number;
  /** The part of `open` that is past its due date. */
  overdue: number;
}

/** One month of the revenue/margin trend. `label` is pre-formatted ("Jul 26"). */
export interface MonthPoint {
  month: string;
  label: string;
  revenue: number;
  margin: number;
}

/** Per-customer profitability, payment behaviour and 0-100 risk score. */
export interface CustomerInsight {
  customer: string;
  revenue: number;
  margin: number;
  marginPct: number;
  openAmount: number;
  overdueAmount: number;
  avgDaysOverdue: number;
  /** Share of this customer's invoices financed by Finqle, 0-1. */
  finqleShare: number;
  shipments: number;
  /** 0-100. Overdue share 40, days overdue 30, thin margin 15, low Finqle 15. */
  riskScore: number;
  revShare: number;
}

// ---------------------------------------------------------------------------
// Performance tab — GET /api/dashboard/performance/
// ---------------------------------------------------------------------------

export interface PerformanceKpis {
  grossRevenue: number;
  marginRevenue: number;
  marginPct: number;
  shipments: number;
  revenuePerShipment: number;
  marginPerShipment: number;
  /** Mean days from the deal's Unload_date to its first final invoice; signed. */
  avgDaysDeliveryToInvoice: number;
  /** How many deals that average covers (unload date and an invoice both present). */
  deliveryToInvoiceDeals: number;
}

/** Month-over-month deltas as fractions (0.12 = +12%). */
export interface MomGrowth {
  revenue: number;
  margin: number;
}

/** A bubble in the revenue-vs-margin scatter. Bubble size `z` = shipments. */
export interface ProfitabilityPoint {
  x: number;
  y: number;
  z: number;
  customer: string;
  marginPct: number;
}

/** One customer x broker cell of the performance detail table. */
export interface PerformanceTableRow {
  customer: string;
  broker: string;
  revenue: number;
  margin: number;
  shipments: number;
}

/** A deal sold below cost. `id` is the short deal number, not Bubble's `_id`. */
export interface NegativeMarginDeal {
  id: string;
  customer: string;
  salesPrice: number;
  margin: number;
}

export interface PerformancePayload {
  kpis: PerformanceKpis;
  mom: MomGrowth;
  trend: MonthPoint[];
  /** All brokers, revenue descending. */
  byBroker: GroupRow[];
  /** Top 10 customers by revenue. */
  byCustomer: GroupRow[];
  /** Top 10 customers by absolute margin. */
  marginRanking: CustomerInsight[];
  scatter: ProfitabilityPoint[];
  /** Every customer x broker pair, revenue descending. */
  table: PerformanceTableRow[];
  /** Deals with a margin below zero, biggest loss first. */
  negativeMarginDeals: NegativeMarginDeal[];
}

// ---------------------------------------------------------------------------
// Receivables tab — GET /api/dashboard/receivables/
// ---------------------------------------------------------------------------

export interface ReceivablesKpis {
  openAmount: number;
  overdueAmount: number;
  overduePct: number;
  openCount: number;
  overdueCount: number;
  avgDaysOverdue: number;
  /** Days overdue of the single oldest outstanding invoice. */
  oldest: number;
  finqleOpen: number;
  nonFinqleOpen: number;
  finqleOverdue: number;
  nonFinqleOverdue: number;
  /** Open receivable Finqle does not carry — the direct Brocarga risk. */
  brocargaExposure: number;
  finqleSharePct: number;
}

/** One aging bucket: "Current", "1-7 days", ... "90+ days". */
export interface AgingBucket {
  bucket: string;
  amount: number;
  count: number;
}

export interface OpenOverdueMonth {
  month: string;
  label: string;
  open: number;
  overdue: number;
}

/** Slice of the Finqle / non-Finqle donut. */
export interface SplitSlice {
  name: string;
  value: number;
}

/**
 * One row of the collections worklist. Deliberately narrower than the full
 * invoice record — payment terms, currency and cost stay server side; the
 * complete extract is /api/transactions/export/.
 */
export interface OutstandingInvoice {
  invoiceNumber: string;
  customer: string;
  broker: string;
  invoiceDate: string;
  dueDate: string;
  outstandingAmount: number;
  status: InvoiceStatus;
  daysOverdue: number;
  financedByFinqle: boolean;
}

export interface ReceivablesPayload {
  kpis: ReceivablesKpis;
  aging: AgingBucket[];
  openVsOverdueByMonth: OpenOverdueMonth[];
  /** Top 10 customers by open amount. */
  openByCustomer: GroupRow[];
  /** Top 10 customers by overdue amount. */
  overdueByCustomer: GroupRow[];
  finqleSplit: SplitSlice[];
  /** Up to 500 outstanding invoices, most overdue first. */
  invoices: OutstandingInvoice[];
  /** True when more outstanding invoices exist than the table carries. */
  invoicesTruncated: boolean;
  /** How many outstanding invoices matched the filters in total. */
  invoicesTotal: number;
}

// ---------------------------------------------------------------------------
// Customer insights tab — GET /api/dashboard/customers/
// ---------------------------------------------------------------------------

export interface CustomerKpis {
  /** Revenue-weighted, not a plain average of percentages. */
  avgMarginPct: number;
  avgDaysOverdue: number;
  highRiskCount: number;
  strategicCount: number;
  customerCount: number;
}

/** Quadrant boundaries for the segmentation matrix. */
export interface Benchmarks {
  marginPct: number;
  daysOverdue: number;
}

/** A bubble in the segmentation matrix: margin % vs days late, sized by revenue. */
export interface SegmentationPoint {
  x: number;
  y: number;
  z: number;
  customer: string;
  riskScore: number;
}

/** One entry of the prioritised collections worklist. */
export interface CollectionAction {
  customer: string;
  overdueAmount: number;
  avgDaysOverdue: number;
  finqleShare: number;
  revenue: number;
  /** 0-100. Revenue at stake 30, days overdue 30, balance 25, unfinanced 15. */
  priority: number;
  /** Escalation label, from "Send Reminder" up to "Consider Credit Hold". */
  action: string;
  actionTone: ActionTone;
}

export interface CustomersPayload {
  kpis: CustomerKpis;
  benchmarks: Benchmarks;
  segmentation: SegmentationPoint[];
  /** Every customer, revenue descending. */
  ranked: CustomerInsight[];
  /** Only customers with an overdue balance, priority descending. */
  actions: CollectionAction[];
}

// ---------------------------------------------------------------------------
// All three tabs at once — GET /api/dashboard/
// ---------------------------------------------------------------------------

/**
 * The whole cockpit for one filter set.
 *
 * Each key is byte-for-byte what the matching per-tab endpoint would return —
 * the backend builds them from a single filtered slice, so nothing here can
 * disagree with anything there.
 */
// ---------------------------------------------------------------------------
// Broker KPIs portfolio tab — GET /api/dashboard/portfolio/
// ---------------------------------------------------------------------------

export interface PortfolioKpis {
  revenue: number;
  margin: number;
  marginPct: number;
  shipments: number;
  /** Deals currently in status "Invoiced"; ignores the deal-status filter. */
  invoicedDeals: number;
  /** Deals currently in status "Transport service"; ignores the deal-status filter. */
  transportServiceDeals: number;
}

/** A customer's Finqle credit facility, from the Bubble Relation. */
export interface CreditLimitRow {
  customer: string;
  creditLimit: number;
  workInProgress: number;
}

export interface PortfolioPayload {
  kpis: PortfolioKpis;
  /**
   * Customers with a Finqle credit limit, largest first. Filtered by customer,
   * and by broker as "held any role on any of the customer's deals, ever";
   * the period does not apply.
   */
  creditLimits: CreditLimitRow[];
}

export interface DashboardPayload {
  performance: PerformancePayload;
  receivables: ReceivablesPayload;
  customers: CustomersPayload;
}

// ---------------------------------------------------------------------------
// Empty payloads
// ---------------------------------------------------------------------------

export const EMPTY_META: MetaResponse = {
  brokers: [],
  customers: [],
  // Kept populated: the status filter is a fixed enum, not a property of the
  // loaded rows, so it stays usable while the dataset is empty.
  statuses: ["Open", "Overdue", "Paid", "Partially Paid", "Disputed"],
  // Unknown until the API answers; the filter bar falls back to the constant.
  dealStatuses: [],
  defaultDealStatus: DEFAULT_DEAL_STATUS,
  asOf: "",
  periods: ["day", "week", "4weeks", "month", "quarter", "year", "all", "custom"],
  source: "",
  fetchedAt: null,
};

export const EMPTY_PERFORMANCE: PerformancePayload = {
  kpis: {
    grossRevenue: 0,
    marginRevenue: 0,
    marginPct: 0,
    shipments: 0,
    revenuePerShipment: 0,
    marginPerShipment: 0,
    avgDaysDeliveryToInvoice: 0,
    deliveryToInvoiceDeals: 0,
  },
  mom: { revenue: 0, margin: 0 },
  trend: [],
  byBroker: [],
  byCustomer: [],
  marginRanking: [],
  scatter: [],
  table: [],
  negativeMarginDeals: [],
};

export const EMPTY_RECEIVABLES: ReceivablesPayload = {
  kpis: {
    openAmount: 0,
    overdueAmount: 0,
    overduePct: 0,
    openCount: 0,
    overdueCount: 0,
    avgDaysOverdue: 0,
    oldest: 0,
    finqleOpen: 0,
    nonFinqleOpen: 0,
    finqleOverdue: 0,
    nonFinqleOverdue: 0,
    brocargaExposure: 0,
    finqleSharePct: 0,
  },
  aging: [],
  openVsOverdueByMonth: [],
  openByCustomer: [],
  overdueByCustomer: [],
  finqleSplit: [],
  invoices: [],
  invoicesTruncated: false,
  invoicesTotal: 0,
};

export const EMPTY_CUSTOMERS: CustomersPayload = {
  kpis: {
    avgMarginPct: 0,
    avgDaysOverdue: 0,
    highRiskCount: 0,
    strategicCount: 0,
    customerCount: 0,
  },
  // The quadrant lines are a fixed policy, not derived from data, so the
  // segmentation chart keeps its reference lines even with nothing plotted.
  benchmarks: { marginPct: 0.12, daysOverdue: 15 },
  segmentation: [],
  ranked: [],
  actions: [],
};

export const EMPTY_PORTFOLIO: PortfolioPayload = {
  kpis: {
    revenue: 0,
    margin: 0,
    marginPct: 0,
    shipments: 0,
    invoicedDeals: 0,
    transportServiceDeals: 0,
  },
  creditLimits: [],
};

export const EMPTY_DASHBOARD: DashboardPayload = {
  performance: EMPTY_PERFORMANCE,
  receivables: EMPTY_RECEIVABLES,
  customers: EMPTY_CUSTOMERS,
};
