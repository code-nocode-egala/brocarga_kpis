import { useEffect, useState } from "react";
import { BarChart3, Briefcase, UserX } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppShell, TAB_TRIGGER_CLASS } from "@/components/dashboard/AppShell";
import { FilterBar, DEFAULT_FILTERS, type Filters } from "@/components/dashboard/FilterBar";
import { BrokerPerformanceTab } from "@/components/dashboard/BrokerPerformanceTab";
import { PortfolioTab } from "@/components/dashboard/PortfolioTab";
import { ApiError, useMeta } from "@/lib/api";

/**
 * Broker KPIs dashboard, served at /broker_kpis?broker=<name>.
 *
 * Bubble opens it with the logged-in broker's name. Every API call carries
 * that name as `viewer`, and the backend limits the data to that broker and
 * their trainees. Without a name the page shows nothing.
 *
 * Uses the same API and filter state as the finance cockpit. The deal-status
 * filter is hidden but still applied at its default, so the numbers match the
 * cockpit's for the same period, brokers and customers.
 */
export function BrokerKpisApp() {
  const viewer = new URLSearchParams(window.location.search).get("broker")?.trim() ?? "";

  useEffect(() => {
    document.title = "Brocarga — Broker KPIs";
  }, []);

  return (
    <AppShell subtitle="Broker KPIs">
      {viewer ? (
        <BrokerDashboard viewer={viewer} />
      ) : (
        <Notice title="No broker specified" message="Open this dashboard from Bubble." />
      )}
    </AppShell>
  );
}

function BrokerDashboard({ viewer }: { viewer: string }) {
  // Opens on the viewer's own numbers; the trainees are one click away.
  const [filters, setFilters] = useState<Filters>({ ...DEFAULT_FILTERS, viewer, brokers: [viewer] });
  const { data: metaData, query: meta } = useMeta(viewer);

  // The link's name matches case-insensitively on the backend, but the filter
  // needs the exact spelling to tick the right checkbox.
  const self = metaData.brokers.find((b) => b.toLowerCase() === viewer.toLowerCase());
  useEffect(() => {
    if (!self || self === viewer) return;
    setFilters((f) => (f.brokers.length === 1 && f.brokers[0] === viewer ? { ...f, brokers: [self] } : f));
  }, [self, viewer]);

  if (meta.error instanceof ApiError && meta.error.status === 403) {
    return <Notice title="Unknown broker" message={`No broker named "${viewer}" was found.`} />;
  }

  return (
    <>
      <FilterBar filters={filters} onChange={setFilters} showDealStatus={false} resetBrokers={[self ?? viewer]} />

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
    </>
  );
}

function Notice({ title, message }: { title: string; message: string }) {
  return (
    <div className="card-elevated flex flex-col items-center gap-2 px-4 py-16 text-center">
      <UserX className="h-8 w-8 text-muted-foreground" />
      <h2 className="font-display text-base font-semibold">{title}</h2>
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
