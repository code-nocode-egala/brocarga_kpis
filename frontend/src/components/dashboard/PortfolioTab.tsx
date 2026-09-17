import { DollarSign, TrendingUp, Percent, Package, FileText, Truck } from "lucide-react";
import type { Filters } from "@/components/dashboard/FilterBar";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { EmptyRows } from "@/components/dashboard/EmptyState";
import { RevenueMarginMatrix } from "@/components/dashboard/RevenueMarginMatrix";
import { usePortfolio } from "@/lib/api";
import { fmtCompact, fmtCurrency, fmtNumber, fmtPct } from "@/lib/format";

/** Portfolio tab of the Broker KPIs page. */
export function PortfolioTab({ filters }: { filters: Filters }) {
  const { kpis, matrix, creditLimits } = usePortfolio(filters).data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Revenue" value={fmtCompact(kpis.revenue)} icon={DollarSign} tone="info" />
        <KpiCard label="Absolute Margin" value={fmtCompact(kpis.margin)} icon={TrendingUp} tone="success" />
        <KpiCard label="Margin %" value={fmtPct(kpis.marginPct)} icon={Percent} tone="success" />
        <KpiCard label="Shipments" value={fmtNumber(kpis.shipments)} icon={Package} tone="default" />
        <KpiCard label="Deals Invoiced" value={fmtNumber(kpis.invoicedDeals)} icon={FileText} tone="warning" />
        <KpiCard label="Deals in Transport Service" value={fmtNumber(kpis.transportServiceDeals)} icon={Truck} tone="info" />
      </div>

      <RevenueMarginMatrix matrix={matrix} />

      <div className="card-elevated overflow-hidden">
        <div className="border-b border-border px-4 py-3">
          <h3 className="font-display text-sm font-semibold">Finqle Credit Limit</h3>
          <p className="text-xs text-muted-foreground">Current credit facility per customer · not affected by the period filter</p>
        </div>
        <div className="max-h-[440px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <Th>Customer</Th><Th right>Credit Limit</Th><Th right>Work in Progress</Th>
              </tr>
            </thead>
            <tbody>
              {creditLimits.map((r, i) => (
                <tr key={i} className="border-t border-border/60 hover:bg-muted/40">
                  <Td className="font-medium">{r.customer}</Td>
                  <Td right>{fmtCurrency(r.creditLimit)}</Td>
                  <Td right>{fmtCurrency(r.workInProgress)}</Td>
                </tr>
              ))}
              <EmptyRows show={creditLimits.length === 0} colSpan={3} message="No customers with a Finqle credit limit." />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`px-4 py-2.5 text-left font-medium whitespace-nowrap ${right ? "text-right" : ""}`}>{children}</th>;
}
function Td({ children, right, className = "" }: { children: React.ReactNode; right?: boolean; className?: string }) {
  return <td className={`px-4 py-2.5 tabular-nums ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
