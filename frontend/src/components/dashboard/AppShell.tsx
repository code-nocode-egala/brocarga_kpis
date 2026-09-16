import { useEffect, useState, type ReactNode } from "react";
import { Activity, Moon, Printer, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Tab trigger styling shared by every dashboard page. */
export const TAB_TRIGGER_CLASS =
  "gap-1.5 rounded-lg text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm md:text-sm md:px-4";

/** Page chrome shared by the dashboards: sticky header, content column, footer. */
export function AppShell({ subtitle, children }: { subtitle: string; children: ReactNode }) {
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
              <p className="text-[11px] text-muted-foreground">{subtitle}</p>
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
        {children}

        <footer className="pt-6 pb-4 text-center text-xs text-muted-foreground">
          Brocarga {subtitle} · Data sources: BOSS & Finqle
        </footer>
      </main>
    </div>
  );
}
