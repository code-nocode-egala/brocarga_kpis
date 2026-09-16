import { useState } from "react";
import { BarChart3, Users2, Wallet } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppShell, TAB_TRIGGER_CLASS } from "@/components/dashboard/AppShell";
import { FilterBar, DEFAULT_FILTERS, type Filters } from "@/components/dashboard/FilterBar";
import { PerformanceTab } from "@/components/dashboard/PerformanceTab";
import { ReceivablesTab } from "@/components/dashboard/ReceivablesTab";
import { CustomerTab } from "@/components/dashboard/CustomerTab";

export function App() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  return (
    <AppShell subtitle="Finance Performance Cockpit">
      <FilterBar filters={filters} onChange={setFilters} />

      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList className="grid h-11 w-full grid-cols-3 rounded-xl border border-border bg-card p-1 md:w-auto md:inline-grid">
          <TabsTrigger
            value="performance"
            className={TAB_TRIGGER_CLASS}
          >
            <BarChart3 className="h-4 w-4" /> Performance
          </TabsTrigger>
          <TabsTrigger
            value="receivables"
            className={TAB_TRIGGER_CLASS}
          >
            <Wallet className="h-4 w-4" /> Receivables & Cashflow
          </TabsTrigger>
          <TabsTrigger
            value="customers"
            className={TAB_TRIGGER_CLASS}
          >
            <Users2 className="h-4 w-4" /> Customer Insights
          </TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="mt-0 focus-visible:outline-none">
          <PerformanceTab filters={filters} />
        </TabsContent>
        <TabsContent value="receivables" className="mt-0 focus-visible:outline-none">
          <ReceivablesTab filters={filters} />
        </TabsContent>
        <TabsContent value="customers" className="mt-0 focus-visible:outline-none">
          <CustomerTab filters={filters} />
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}
