import { useMemo, useState } from "react";
import { CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowUp, ArrowUpDown, Users, Percent, Clock, AlertTriangle, Star, Download, Zap, Phone, Mail, ShieldAlert, ArrowUpCircle, XCircle } from "lucide-react";
import type { Filters } from "@/components/dashboard/FilterBar";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ChartCard } from "@/components/dashboard/ChartCard";
import { EmptyRows } from "@/components/dashboard/EmptyState";
import { useCustomers } from "@/lib/api";
import type { ActionTone, CustomerInsight } from "@/lib/api-types";
import { fmtCompact, fmtCurrency, fmtNumber, fmtPct } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { toCsv } from "@/lib/export";

/** How many rows of the prioritised worklist fit on screen before it stops being a worklist. */
const ACTION_LIMIT = 15;

type SortKey = "customer" | "revenue" | "margin" | "marginPct" | "openAmount" | "overdueAmount" | "avgDaysOverdue" | "finqleShare" | "riskScore";
type SortState = { key: SortKey; dir: "asc" | "desc" } | null;

/**
 * Next state for a header click: text columns start ascending, numbers
 * descending; the second click flips it and the third returns to the
 * backend's own ranking order.
 */
function nextSort(current: SortState, key: SortKey): SortState {
  const first = key === "customer" ? "asc" : "desc";
  if (current?.key !== key) return { key, dir: first };
  if (current.dir === first) return { key, dir: first === "asc" ? "desc" : "asc" };
  return null;
}

function sortRows(rows: CustomerInsight[], sort: SortState): CustomerInsight[] {
  if (!sort) return rows;
  const { key, dir } = sort;
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) =>
    key === "customer"
      ? sign * a.customer.localeCompare(b.customer)
      : sign * ((a[key] as number) - (b[key] as number)),
  );
}

/**
 * Icon per escalation label. The backend owns the ladder — which label a
 * customer earns and how severe it is (`actionTone`) — and this map only
 * decides what it looks like. An unrecognised label still renders, with the
 * neutral icon, rather than breaking the row.
 */
const ACTION_ICONS: Record<string, LucideIcon> = {
  "Consider Credit Hold": XCircle,
  "Escalate to Management": ShieldAlert,
  "Review Credit Exposure": ShieldAlert,
  "Escalate to Broker": ArrowUpCircle,
  "Contact Customer": Phone,
  "Send Reminder": Mail,
};

const ACTION_TONES: Record<ActionTone, string> = {
  destructive: "bg-destructive/10 text-destructive",
  warning: "bg-warning/20 text-warning-foreground",
  default: "bg-primary/10 text-primary",
};

export function CustomerTab({ filters }: { filters: Filters }) {
  // Segmentation, ranking and the action list all arrive finished from
  // `build_customers`, including the risk and priority scores and the quadrant
  // benchmarks the reference lines are drawn at.
  const { data } = useCustomers(filters);
  const { kpis, benchmarks, segmentation, ranked, actions } = data;

  const marginBenchmark = benchmarks.marginPct;
  const daysBenchmark = benchmarks.daysOverdue;
  const topActions = actions.slice(0, ACTION_LIMIT);

  const [sort, setSort] = useState<SortState>(null);
  const sortedRanked = useMemo(() => sortRows(ranked, sort), [ranked, sort]);
  const sortProps = (key: SortKey) => ({ sortKey: key, sort, onSort: (k: SortKey) => setSort((s) => nextSort(s, k)) });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <KpiCard label="Active Customers" value={fmtNumber(kpis.customerCount)} icon={Users} tone="info" />
        <KpiCard label="Avg Margin %" value={fmtPct(kpis.avgMarginPct)} icon={Percent} tone="success" />
        <KpiCard label="Avg Days Overdue" value={`${Math.round(kpis.avgDaysOverdue)}d`} icon={Clock} tone={kpis.avgDaysOverdue > 20 ? "danger" : "warning"} />
        <KpiCard label="High Risk Customers" value={fmtNumber(kpis.highRiskCount)} icon={AlertTriangle} tone="danger" />
        <KpiCard label="Strategic Customers" value={fmtNumber(kpis.strategicCount)} icon={Star} tone="success" />
      </div>

      <ChartCard title="Customer Segmentation Matrix" subtitle="Margin % vs. average days overdue — bubble size = revenue">
        <div className="h-[380px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 12, right: 24, left: 8, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis type="number" dataKey="x" name="Margin %" unit="%" domain={[0, 30]} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} label={{ value: "Margin %", position: "insideBottom", offset: -8, fill: "var(--color-muted-foreground)", fontSize: 11 }} />
              <YAxis type="number" dataKey="y" name="Avg Days Overdue" unit="d" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} label={{ value: "Avg Days Overdue", angle: -90, position: "insideLeft", fill: "var(--color-muted-foreground)", fontSize: 11 }} />
              <ZAxis type="number" dataKey="z" range={[120, 900]} />
              <ReferenceLine x={marginBenchmark * 100} stroke="var(--color-muted-foreground)" strokeDasharray="4 4" />
              <ReferenceLine y={daysBenchmark} stroke="var(--color-muted-foreground)" strokeDasharray="4 4" />
              <Tooltip content={<SegTT />} cursor={{ strokeDasharray: "3 3" }} />
              <Scatter data={segmentation} fillOpacity={0.75}>
                {segmentation.map((p) => {
                  const highMargin = p.x >= marginBenchmark * 100;
                  const onTime = p.y <= daysBenchmark;
                  const fill = highMargin && onTime ? "var(--color-success)"
                    : highMargin && !onTime ? "var(--color-chart-3)"
                    : !highMargin && onTime ? "var(--color-chart-1)"
                    : "var(--color-destructive)";
                  return <Cell key={p.customer} fill={fill} />;
                })}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
          <QuadLegend color="bg-success" label="High margin · On time" desc="Ideal customers" />
          <QuadLegend color="bg-chart-3" label="High margin · Slow payer" desc="Cashflow risk" />
          <QuadLegend color="bg-chart-1" label="Low margin · On time" desc="Efficiency opportunity" />
          <QuadLegend color="bg-destructive" label="Low margin · Slow payer" desc="Highest risk" />
        </div>
      </ChartCard>

      <div className="card-elevated overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h3 className="font-display text-sm font-semibold">Customer Ranking</h3>
            <p className="text-xs text-muted-foreground">Profitability, payment behaviour and risk score</p>
          </div>
          <Button size="sm" variant="outline" className="gap-1.5" disabled={ranked.length === 0} onClick={() => toCsv(sortedRanked, "customer-ranking.csv")}>
            <Download className="h-3.5 w-3.5" /> Export CSV
          </Button>
        </div>
        <div className="max-h-[440px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <SortTh {...sortProps("customer")}>Customer</SortTh>
                <SortTh right {...sortProps("revenue")}>Revenue</SortTh>
                <SortTh right {...sortProps("margin")}>Margin</SortTh>
                <SortTh right {...sortProps("marginPct")}>Margin %</SortTh>
                <SortTh right {...sortProps("openAmount")}>Open</SortTh>
                <SortTh right {...sortProps("overdueAmount")}>Overdue</SortTh>
                <SortTh right {...sortProps("avgDaysOverdue")}>Avg Days Overdue</SortTh>
                <SortTh right {...sortProps("finqleShare")}>Finqle Usage</SortTh>
                <SortTh right {...sortProps("riskScore")}>Risk Score</SortTh>
              </tr>
            </thead>
            <tbody>
              {sortedRanked.map((c) => (
                <tr key={c.customer} className="border-t border-border/60 hover:bg-muted/40">
                  <Td className="font-medium">{c.customer}</Td>
                  <Td right>{fmtCurrency(c.revenue)}</Td>
                  <Td right>{fmtCurrency(c.margin)}</Td>
                  <Td right>
                    <span className={`inline-flex rounded-md px-1.5 py-0.5 text-xs font-medium ${c.marginPct >= 0.15 ? "bg-success/15 text-success" : c.marginPct >= 0.08 ? "bg-warning/20 text-warning-foreground" : "bg-destructive/10 text-destructive"}`}>
                      {fmtPct(c.marginPct)}
                    </span>
                  </Td>
                  <Td right>{fmtCurrency(c.openAmount)}</Td>
                  <Td right className={c.overdueAmount > 0 ? "text-destructive" : ""}>{fmtCurrency(c.overdueAmount)}</Td>
                  <Td right>{Math.round(c.avgDaysOverdue)}d</Td>
                  <Td right>{fmtPct(c.finqleShare, 0)}</Td>
                  <Td right>
                    <RiskBar score={c.riskScore} />
                  </Td>
                </tr>
              ))}
              <EmptyRows show={ranked.length === 0} colSpan={9} message="No customers in this period." />
            </tbody>
          </table>
        </div>
      </div>

      <div className="card-elevated overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h3 className="font-display text-sm font-semibold flex items-center gap-2">
              <Zap className="h-4 w-4 text-warning" /> Action List
            </h3>
            <p className="text-xs text-muted-foreground">
              {actions.length > ACTION_LIMIT
                ? `Top ${ACTION_LIMIT} of ${fmtNumber(actions.length)} customers requiring attention, sorted by priority`
                : "Customers requiring immediate attention, sorted by priority"}
            </p>
          </div>
        </div>
        <div className="max-h-[520px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <Th right>Priority</Th><Th>Customer</Th><Th right>Outstanding</Th>
                <Th right>Days Overdue</Th><Th right>Revenue Contribution</Th>
                <Th right>Finqle Usage</Th><Th>Recommended Action</Th>
              </tr>
            </thead>
            <tbody>
              {topActions.map((a) => {
                const Icon = ACTION_ICONS[a.action] ?? Mail;
                return (
                  <tr key={a.customer} className="border-t border-border/60 hover:bg-muted/40">
                    <Td right>
                      <span className="inline-flex h-7 w-10 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">{a.priority}</span>
                    </Td>
                    <Td className="font-medium">{a.customer}</Td>
                    <Td right className="font-medium">{fmtCurrency(a.overdueAmount)}</Td>
                    <Td right>{Math.round(a.avgDaysOverdue)}d</Td>
                    <Td right>{fmtCompact(a.revenue)}</Td>
                    <Td right>{fmtPct(a.finqleShare, 0)}</Td>
                    <Td>
                      <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${ACTION_TONES[a.actionTone] ?? ACTION_TONES.default}`}>
                        <Icon className="h-3.5 w-3.5" /> {a.action}
                      </span>
                    </Td>
                  </tr>
                );
              })}
              <EmptyRows
                show={topActions.length === 0}
                colSpan={7}
                message="No overdue customers under current filters — nothing to action."
              />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function QuadLegend({ color, label, desc }: { color: string; label: string; desc: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-border/60 bg-muted/30 p-2">
      <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${color}`} />
      <div>
        <div className="text-xs font-medium">{label}</div>
        <div className="text-[11px] text-muted-foreground">{desc}</div>
      </div>
    </div>
  );
}

function RiskBar({ score }: { score: number }) {
  const tone = score >= 70 ? "bg-destructive" : score >= 40 ? "bg-warning" : "bg-success";
  const label = score >= 70 ? "text-destructive" : score >= 40 ? "text-warning-foreground" : "text-success";
  return (
    <div className="inline-flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${tone}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`text-xs font-medium ${label}`}>{score}</span>
    </div>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`px-4 py-2.5 text-left font-medium ${right ? "text-right" : ""}`}>{children}</th>;
}
function SortTh({ children, right, sortKey, sort, onSort }: {
  children: React.ReactNode; right?: boolean; sortKey: SortKey; sort: SortState; onSort: (k: SortKey) => void;
}) {
  const active = sort?.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      className={`px-4 py-2.5 font-medium ${right ? "text-right" : "text-left"}`}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex cursor-pointer items-center gap-1 whitespace-nowrap uppercase tracking-wider hover:text-foreground ${active ? "text-foreground" : ""}`}
      >
        {children}
        <Icon className={`h-3 w-3 ${active ? "" : "opacity-40"}`} />
      </button>
    </th>
  );
}
function Td({ children, right, className = "" }: { children: React.ReactNode; right?: boolean; className?: string }) {
  return <td className={`px-4 py-2.5 tabular-nums ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
function SegTT({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium">{p.customer}</div>
      <div className="grid gap-0.5 text-muted-foreground">
        <div>Margin %: <span className="font-medium text-foreground">{p.x.toFixed(1)}%</span></div>
        <div>Avg days overdue: <span className="font-medium text-foreground">{p.y}d</span></div>
        <div>Revenue: <span className="font-medium text-foreground">{fmtCurrency(p.z)}</span></div>
        <div>Risk score: <span className="font-medium text-foreground">{p.riskScore}</span></div>
      </div>
    </div>
  );
}
