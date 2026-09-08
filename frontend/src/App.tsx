import { useEffect, useState } from "react";
import { Activity, BarChart3, Moon, Printer, Sun, Users2, Wallet } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { FilterBar, DEFAULT_FILTERS, type Filters } from "@/components/dashboard/FilterBar";
import { PerformanceTab } from "@/components/dashboard/PerformanceTab";
import { ReceivablesTab } from "@/components/dashboard/ReceivablesTab";
import { CustomerTab } from "@/components/dashboard/CustomerTab";

export function App() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const el = document.documentElement;
    if (dark) el.classList.add("dark");
    else el.classList.remove("dark");
  }, [dark]);

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-4 py-3 lg:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-display text-base font-semibold leading-tight tracking-tight">
                Brocarga
              </h1>
              <p className="text-[11px] text-muted-foreground">Finance Performance Cockpit</p>
            </div>
          </div>

          <div className="hidden items-center gap-4 md:flex">
            <div className="flex items-center gap-2 rounded-full border border-border bg-muted/50 px-3 py-1 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
              Live · BOSS + Finqle
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="gap-1.5" onClick={() => window.print()}>
              <Printer className="h-4 w-4" /> <span className="hidden sm:inline">Export PDF</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDark((d) => !d)}
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] space-y-4 px-4 py-5 lg:px-6">
        <FilterBar filters={filters} onChange={setFilters} />

        <Tabs defaultValue="performance" className="space-y-4">
          <TabsList className="grid h-11 w-full grid-cols-3 rounded-xl border border-border bg-card p-1 md:w-auto md:inline-grid">
            <TabsTrigger
              value="performance"
              className="gap-1.5 rounded-lg text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm md:text-sm md:px-4"
            >
              <BarChart3 className="h-4 w-4" /> Performance
            </TabsTrigger>
            <TabsTrigger
              value="receivables"
              className="gap-1.5 rounded-lg text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm md:text-sm md:px-4"
            >
              <Wallet className="h-4 w-4" /> Receivables & Cashflow
            </TabsTrigger>
            <TabsTrigger
              value="customers"
              className="gap-1.5 rounded-lg text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm md:text-sm md:px-4"
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

        <footer className="pt-6 pb-4 text-center text-xs text-muted-foreground">
          Brocarga Finance Performance Cockpit · Data sources: BOSS & Finqle
        </footer>
      </main>
    </div>
  );
}
