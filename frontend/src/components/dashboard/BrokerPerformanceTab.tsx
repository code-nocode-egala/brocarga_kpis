import { DollarSign, TrendingUp, Percent, Package, Coins, Wallet, CalendarClock } from "lucide-react";
import type { Filters } from "@/components/dashboard/FilterBar";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { EmptyRows } from "@/components/dashboard/EmptyState";
import { RevenueMarginTrend } from "@/components/dashboard/PerformanceTab";
import { usePerformance } from "@/lib/api";
import { fmtCompact, fmtCurrency, fmtNumber, fmtPct } from "@/lib/format";

/** Performance tab of the Broker KPIs page: headline KPIs, the monthly trend and loss-making deals. */
export function BrokerPerformanceTab({ filters }: { filters: Filters }) {
  const { data } = usePerformance(filters);
  const { kpis, mom, trend, negativeMarginDeals } = data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Gross Revenue" value={fmtCompact(kpis.grossRevenue)} trend={mom.revenue} icon={DollarSign} tone="info" />
        <KpiCard label="Margin Revenue" value={fmtCompact(kpis.marginRevenue)} trend={mom.margin} icon={TrendingUp} tone="success" />
        <KpiCard label="Margin %" value={fmtPct(kpis.marginPct)} icon={Percent} tone="success" />
        <KpiCard label="Shipments" value={fmtNumber(kpis.shipments)} icon={Package} tone="default" />
        <KpiCard label="Avg Revenue / Shipment" value={fmtCurrency(kpis.revenuePerShipment)} icon={Coins} tone="info" />
        <KpiCard label="Avg Margin / Shipment" value={fmtCurrency(kpis.marginPerShipment)} icon={Wallet} tone="success" />
        <KpiCard
          label="Avg Days Delivery → Invoice"
          value={`${kpis.avgDaysDeliveryToInvoice.toFixed(1)}d`}
          sublabel={`${fmtNumber(kpis.deliveryToInvoiceDeals)} invoiced deals`}
          icon={CalendarClock}
          tone="info"
        />
      </div>

      <RevenueMarginTrend trend={trend} className="h-[380px]" />

      <div className="card-elevated overflow-hidden">
        <div className="border-b border-border px-4 py-3">
          <h3 className="font-display text-sm font-semibold">Order Lines with Negative Margin</h3>
          <p className="text-xs text-muted-foreground">
            {fmtNumber(negativeMarginDeals.length)} deals sold below cost · biggest loss first
          </p>
        </div>
        <div className="max-h-[440px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/60 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <Th>ID</Th><Th>Customer</Th><Th right>Sales Price</Th><Th right>Margin</Th>
              </tr>
            </thead>
            <tbody>
              {negativeMarginDeals.map((d) => (
                <tr key={d.id} className="border-t border-border/60 hover:bg-muted/40">
                  <Td className="text-muted-foreground">{d.id}</Td>
                  <Td className="font-medium">{d.customer}</Td>
                  <Td right>{fmtCurrency(d.salesPrice)}</Td>
                  <Td right className="font-medium text-destructive">{fmtCurrency(d.margin)}</Td>
                </tr>
              ))}
              <EmptyRows show={negativeMarginDeals.length === 0} colSpan={4} message="No deals with negative margin in this period." />
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
