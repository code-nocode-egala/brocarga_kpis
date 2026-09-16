import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { DollarSign, TrendingUp, Percent, Package, Coins, Wallet, ArrowUpRight, ArrowDownRight, Download } from "lucide-react";
import type { Filters } from "@/components/dashboard/FilterBar";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ChartCard } from "@/components/dashboard/ChartCard";
import { EmptyRows } from "@/components/dashboard/EmptyState";
import { NameTick, firstName, shorten } from "@/components/dashboard/NameTick";
import { usePerformance } from "@/lib/api";
import type { PerformancePayload } from "@/lib/api-types";
import { fmtCompact, fmtCurrency, fmtNumber, fmtPct } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { toCsv } from "@/lib/export";

const CHART = {
  revenue: "var(--color-chart-1)",
  margin: "var(--color-chart-2)",
  warn: "var(--color-chart-3)",
  danger: "var(--color-chart-4)",
};

export function PerformanceTab({ filters }: { filters: Filters }) {
  // Everything below is served pre-aggregated, pre-sorted and pre-truncated by
  // `build_performance`. No useMemo blocks here any more: there is nothing left
  // to recompute, only fields to read.
  const { data } = usePerformance(filters);
  const { kpis, mom, trend, byBroker, byCustomer, marginRanking, scatter, table } = data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-4">
        <KpiCard label="Gross Revenue" value={fmtCompact(kpis.grossRevenue)} trend={mom.revenue} icon={DollarSign} tone="info" />
        <KpiCard label="Margin Revenue" value={fmtCompact(kpis.marginRevenue)} trend={mom.margin} icon={TrendingUp} tone="success" />
        <KpiCard label="Margin %" value={fmtPct(kpis.marginPct)} icon={Percent} tone="success" />
        <KpiCard label="Shipments" value={fmtNumber(kpis.shipments)} icon={Package} tone="default" />
        <KpiCard label="Revenue / Shipment" value={fmtCurrency(kpis.revenuePerShipment)} icon={Coins} tone="info" />
        <KpiCard label="Margin / Shipment" value={fmtCurrency(kpis.marginPerShipment)} icon={Wallet} tone="success" />
        <KpiCard label="MoM Revenue Growth" value={fmtPct(mom.revenue)} icon={mom.revenue >= 0 ? ArrowUpRight : ArrowDownRight} tone={mom.revenue >= 0 ? "success" : "danger"} />
        <KpiCard label="MoM Margin Growth" value={fmtPct(mom.margin)} icon={mom.margin >= 0 ? ArrowUpRight : ArrowDownRight} tone={mom.margin >= 0 ? "success" : "danger"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <RevenueMarginTrend trend={trend} className="xl:col-span-2 h-[340px]" />

        <ChartCard title="Revenue by Broker" className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={byBroker} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="key" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} width={90} />
              <Tooltip content={<TT />} />
              <Bar dataKey="revenue" name="Revenue" fill={CHART.revenue} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <ChartCard title="Margin by Broker" className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={byBroker} margin={{ top: 8, right: 8, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="key" interval={0} tick={<NameTick format={firstName} dy="0.71em" />} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip content={<TT />} />
              <Bar dataKey="margin" name="Margin" fill={CHART.margin} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top 10 Customers by Revenue" className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={byCustomer} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="key" interval={0} tick={<NameTick format={shorten} dy="0.355em" />} axisLine={false} tickLine={false} width={130} />
              <Tooltip content={<TT />} />
              <Bar dataKey="revenue" name="Revenue" fill={CHART.revenue} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top 10 Customers by Margin" className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={marginRanking} layout="vertical" margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="customer" interval={0} tick={<NameTick format={shorten} dy="0.355em" />} axisLine={false} tickLine={false} width={130} />
              <Tooltip content={<TT />} />
              <Bar dataKey="margin" name="Margin" fill={CHART.margin} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title="Revenue vs Margin — Customer Profitability" subtitle="Bubble size = number of shipments" className="h-[380px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis type="number" dataKey="x" name="Revenue" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} />
            <YAxis type="number" dataKey="y" name="Margin" tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} />
            <ZAxis type="number" dataKey="z" range={[60, 500]} />
            <Tooltip content={<ScatterTT />} cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={scatter} fill={CHART.revenue} fillOpacity={0.7} />
          </ScatterChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="card-elevated overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h3 className="font-display text-sm font-semibold">Performance Detail</h3>
            <p className="text-xs text-muted-foreground">Customer × Broker profitability breakdown</p>
          </div>
          <Button size="sm" variant="outline" className="gap-1.5" disabled={table.length === 0} onClick={() => toCsv(table, "performance.csv")}>
            <Download className="h-3.5 w-3.5" /> Export CSV
          </Button>
        </div>
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <Th>Customer</Th><Th>Broker</Th>
                <Th right>Gross Revenue</Th><Th right>Margin</Th><Th right>Margin %</Th>
                <Th right>Shipments</Th><Th right>Rev / Shp</Th><Th right>Margin / Shp</Th>
              </tr>
            </thead>
            <tbody>
              {table.map((r, i) => {
                // Per-row ratios, not aggregation: derived from two fields of the
                // same row purely to render them. Everything summed lives server side.
                const mPct = r.revenue > 0 ? r.margin / r.revenue : 0;
                const perShipment = r.shipments > 0 ? r.revenue / r.shipments : 0;
                const marginPerShipment = r.shipments > 0 ? r.margin / r.shipments : 0;
                return (
                  <tr key={i} className="border-t border-border/60 hover:bg-muted/40">
                    <Td className="font-medium">{r.customer}</Td>
                    <Td className="text-muted-foreground">{r.broker}</Td>
                    <Td right>{fmtCurrency(r.revenue)}</Td>
                    <Td right>{fmtCurrency(r.margin)}</Td>
                    <Td right>
                      <span className={`inline-flex rounded-md px-1.5 py-0.5 text-xs font-medium ${mPct >= 0.15 ? "bg-success/15 text-success" : mPct >= 0.08 ? "bg-warning/20 text-warning-foreground" : "bg-destructive/10 text-destructive"}`}>
                        {fmtPct(mPct)}
                      </span>
                    </Td>
                    <Td right>{fmtNumber(r.shipments)}</Td>
                    <Td right>{fmtCurrency(perShipment)}</Td>
                    <Td right>{fmtCurrency(marginPerShipment)}</Td>
                  </tr>
                );
              })}
              <EmptyRows show={table.length === 0} colSpan={8} message="No shipments in this period." />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/** Monthly gross revenue bars with the margin line; also used on the Broker KPIs page. */
export function RevenueMarginTrend({ trend, className }: { trend: PerformancePayload["trend"]; className?: string }) {
  return (
    <ChartCard title="Revenue & Margin Trend" subtitle="Monthly gross revenue vs. margin revenue" className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={trend} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.revenue} stopOpacity={0.9} />
              <stop offset="100%" stopColor={CHART.revenue} stopOpacity={0.4} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={(v) => fmtCompact(v as number)} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
          <Tooltip content={<TT />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="revenue" name="Revenue" fill="url(#revGrad)" radius={[6, 6, 0, 0]} />
          <Line type="monotone" dataKey="margin" name="Margin" stroke={CHART.margin} strokeWidth={2.5} dot={{ r: 3, fill: CHART.margin }} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
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
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.fill }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium tabular-nums">{typeof p.value === "number" ? fmtCurrency(p.value) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

function ScatterTT({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium">{p.customer}</div>
      <div className="grid gap-0.5 text-muted-foreground">
        <div>Revenue: <span className="font-medium text-foreground">{fmtCurrency(p.x)}</span></div>
        <div>Margin: <span className="font-medium text-foreground">{fmtCurrency(p.y)}</span></div>
        <div>Margin %: <span className="font-medium text-foreground">{fmtPct(p.marginPct)}</span></div>
        <div>Shipments: <span className="font-medium text-foreground">{p.z}</span></div>
      </div>
    </div>
  );
}
