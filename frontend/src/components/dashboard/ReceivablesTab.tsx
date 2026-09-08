import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Clock, FileWarning, Files, Hourglass, Landmark, PiggyBank, Wallet, Download, Search } from "lucide-react";
import type { Filters } from "@/components/dashboard/FilterBar";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ChartCard } from "@/components/dashboard/ChartCard";
import { EmptyRows } from "@/components/dashboard/EmptyState";
import { transactionsExportUrl, useReceivables } from "@/lib/api";
import { fmtCompact, fmtCurrency, fmtDate, fmtNumber, fmtPct } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toCsv } from "@/lib/export";

const AGING_COLORS = [
  "var(--color-success)",
  "var(--color-chart-3)",
  "var(--color-warning)",
  "var(--color-chart-4)",
  "var(--color-destructive)",
  "oklch(0.45 0.20 25)",
];

export function ReceivablesTab({ filters }: { filters: Filters }) {
  // `build_receivables` hands over finished KPIs, the aging split, the trailing
  // 12 months and a worklist of at most 500 outstanding invoices sorted by days
  // overdue. Nothing on this tab is summed in the browser.
  const { data } = useReceivables(filters);
  const { kpis, aging, openVsOverdueByMonth, openByCustomer, overdueByCustomer, finqleSplit } = data;

  // Search stays client side: it narrows the worklist already in hand, so
  // typing does not fire a request per keystroke. Anything beyond the 500-row
  // cap is reached through the full extract, not through this box.
  const [search, setSearch] = useState("");
  const invoiceRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data.invoices;
    return data.invoices.filter((r) =>
      `${r.invoiceNumber} ${r.customer} ${r.broker}`.toLowerCase().includes(q),
    );
  }, [data.invoices, search]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-4">
        <KpiCard
          label="Open Invoice Amount"
          value={fmtCompact(kpis.openAmount)}
          icon={Wallet}
          tone="info"
          sublabel={`${fmtCompact(kpis.finqleOpen)} Finqle · ${fmtCompact(kpis.nonFinqleOpen)} non-Finqle`}
        />
        <KpiCard
          label="Brocarga Direct Exposure"
          value={fmtCompact(kpis.brocargaExposure)}
          icon={Landmark}
          tone={kpis.brocargaExposure > kpis.finqleOpen ? "warning" : "success"}
          sublabel={`Non-financed receivables · ${fmtPct(1 - kpis.finqleSharePct)} of open`}
        />
        <KpiCard
          label="Overdue Amount"
          value={fmtCompact(kpis.overdueAmount)}
          icon={AlertTriangle}
          tone="danger"
          sublabel={`${fmtCompact(kpis.finqleOverdue)} Finqle · ${fmtCompact(kpis.nonFinqleOverdue)} non-Finqle`}
        />
        <KpiCard label="Overdue %" value={fmtPct(kpis.overduePct)} icon={FileWarning} tone={kpis.overduePct > 0.25 ? "danger" : kpis.overduePct > 0.1 ? "warning" : "success"} />
        <KpiCard label="Avg Days Overdue" value={`${Math.round(kpis.avgDaysOverdue)}d`} icon={Clock} tone={kpis.avgDaysOverdue > 30 ? "danger" : "warning"} />
        <KpiCard label="Open Invoices" value={fmtNumber(kpis.openCount)} icon={Files} tone="default" sublabel={`${fmtNumber(kpis.overdueCount)} overdue`} />
        <KpiCard label="Oldest Outstanding" value={`${kpis.oldest}d`} icon={Hourglass} tone={kpis.oldest > 60 ? "danger" : "warning"} />
        <KpiCard
          label="Finqle Financed (open)"
          value={fmtCompact(kpis.finqleOpen)}
          icon={PiggyBank}
          tone="success"
          sublabel={`${fmtPct(kpis.finqleSharePct)} of open receivables`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <ChartCard title="Open vs Overdue — Trailing 12 Months" className="xl:col-span-2 h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={openVsOverdueByMonth} margin={{ top: 8, right: 8, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="open" name="Open" stackId="a" fill="var(--color-chart-1)" radius={[0, 0, 0, 0]} />
              <Bar dataKey="overdue" name="Overdue" stackId="a" fill="var(--color-destructive)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Aging Analysis" subtitle="Outstanding by age bucket" className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={aging} dataKey="amount" nameKey="bucket" innerRadius={60} outerRadius={100} paddingAngle={2}>
                {aging.map((b, i) => <Cell key={b.bucket} fill={AGING_COLORS[i % AGING_COLORS.length]} />)}
              </Pie>
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <ChartCard title="Open Amount by Customer" className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={openByCustomer} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="key" tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} width={130} />
              <Tooltip content={<TT />} />
              <Bar dataKey="open" name="Open" fill="var(--color-chart-1)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Overdue Amount by Customer" className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={overdueByCustomer} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="key" tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} width={130} />
              <Tooltip content={<TT />} />
              <Bar dataKey="overdue" name="Overdue" fill="var(--color-destructive)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Finqle vs Non-Finqle Outstanding" className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={finqleSplit} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} paddingAngle={2}>
                {finqleSplit.map((s, i) => (
                  <Cell key={s.name} fill={i === 0 ? "var(--color-success)" : "var(--color-chart-3)"} />
                ))}
              </Pie>
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="card-elevated overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
          <div>
            <h3 className="font-display text-sm font-semibold">Outstanding Invoice Detail</h3>
            <p className="text-xs text-muted-foreground">
              {data.invoicesTruncated
                ? `Showing ${fmtNumber(invoiceRows.length)} of ${fmtNumber(data.invoicesTotal)} outstanding invoices`
                : `Showing ${fmtNumber(invoiceRows.length)} outstanding invoices`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search invoice / customer / broker" className="h-8 w-72 pl-7 text-xs" />
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5"
              disabled={invoiceRows.length === 0}
              onClick={() => toCsv(invoiceRows, "outstanding-invoices.csv")}
            >
              <Download className="h-3.5 w-3.5" /> Export CSV
            </Button>
            {/* Only offered once the worklist is capped — otherwise the CSV above
                already holds everything the filters matched. */}
            {data.invoicesTruncated && (
              <Button size="sm" variant="ghost" className="gap-1.5" asChild>
                <a href={transactionsExportUrl(filters)} download>
                  <Download className="h-3.5 w-3.5" /> Full extract
                </a>
              </Button>
            )}
          </div>
        </div>
        <div className="max-h-[520px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <Th>Invoice</Th><Th>Customer</Th><Th>Broker</Th>
                <Th>Invoice Date</Th><Th>Due Date</Th>
                <Th right>Outstanding</Th><Th right>Days Overdue</Th>
                <Th>Finqle</Th><Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {invoiceRows.map((r) => {
                const d = r.daysOverdue;
                const tone = d === 0 ? "bg-success/15 text-success" : d <= 30 ? "bg-warning/20 text-warning-foreground" : "bg-destructive/10 text-destructive";
                return (
                  <tr key={r.invoiceNumber} className="border-t border-border/60 hover:bg-muted/40">
                    <Td className="font-medium">{r.invoiceNumber}</Td>
                    <Td>{r.customer}</Td>
                    <Td className="text-muted-foreground">{r.broker}</Td>
                    <Td>{fmtDate(r.invoiceDate)}</Td>
                    <Td>{fmtDate(r.dueDate)}</Td>
                    <Td right className="font-medium">{fmtCurrency(r.outstandingAmount)}</Td>
                    <Td right>
                      <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium ${tone}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${d === 0 ? "bg-success" : d <= 30 ? "bg-warning" : "bg-destructive"}`} />
                        {d === 0 ? "Current" : `${d}d`}
                      </span>
                    </Td>
                    <Td>
                      {r.financedByFinqle ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-success/15 px-1.5 py-0.5 text-xs font-medium text-success">
                          <PiggyBank className="h-3 w-3" /> Yes
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">No</span>
                      )}
                    </Td>
                    <Td><span className="text-xs">{r.status}</span></Td>
                  </tr>
                );
              })}
              <EmptyRows
                show={invoiceRows.length === 0}
                colSpan={9}
                message={search ? "No outstanding invoice matches that search." : "No outstanding invoices in this period."}
              />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`px-4 py-2.5 text-left font-medium ${right ? "text-right" : ""}`}>{children}</th>;
}
function Td({ children, right, className = "" }: { children: React.ReactNode; right?: boolean; className?: string }) {
  return <td className={`px-4 py-2.5 tabular-nums ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
function TT({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
      {label && <div className="mb-1 font-medium">{label}</div>}
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.payload?.fill }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium tabular-nums">{fmtCurrency(p.value as number)}</span>
        </div>
      ))}
    </div>
  );
}
