import { useEffect, useState } from "react";
import { BarChart3, Briefcase } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppShell, TAB_TRIGGER_CLASS } from "@/components/dashboard/AppShell";
import { FilterBar, DEFAULT_FILTERS, type Filters } from "@/components/dashboard/FilterBar";
import { BrokerPerformanceTab } from "@/components/dashboard/BrokerPerformanceTab";
import { PortfolioTab } from "@/components/dashboard/PortfolioTab";

/**
 * Broker KPIs dashboard, served at /broker_kpis.
 *
 * Open to everyone: it starts on all brokers, and the broker filter offers
 * every broker in the snapshot.
 *
 * Uses the same API and filter state as the finance cockpit. The deal-status
 * filter is hidden but still applied at its default, so the numbers match the
 * cockpit's for the same period, brokers and customers.
 */
export function BrokerKpisApp() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  useEffect(() => {
    document.title = "Brocarga — Broker KPIs";
  }, []);

  return (
    <AppShell subtitle="Broker KPIs">
      <FilterBar filters={filters} onChange={setFilters} showDealStatus={false} />

      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList className="grid h-11 w-full grid-cols-2 rounded-xl border border-border bg-card p-1 md:w-auto md:inline-grid">
          <TabsTrigger value="performance" className={TAB_TRIGGER_CLASS}>
            <BarChart3 className="h-4 w-4" /> Performance
          </TabsTrigger>
          <TabsTrigger value="portfolio" className={TAB_TRIGGER_CLASS}>
            <Briefcase className="h-4 w-4" /> Portfolio
          </TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="mt-0 focus-visible:outline-none">
          <BrokerPerformanceTab filters={filters} />
        </TabsContent>
        <TabsContent value="portfolio" className="mt-0 focus-visible:outline-none">
          <PortfolioTab filters={filters} />
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}
