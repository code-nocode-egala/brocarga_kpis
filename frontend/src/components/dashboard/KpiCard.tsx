import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  trend?: number; // fraction, e.g. 0.12 = +12%
  icon?: LucideIcon;
  tone?: "default" | "success" | "warning" | "danger" | "info";
  invertTrend?: boolean; // for KPIs where "down" is good (e.g. overdue)
}

export function KpiCard({ label, value, sublabel, trend, icon: Icon, tone = "default", invertTrend }: KpiCardProps) {
  const trendPositive = trend !== undefined && trend > 0;
  const trendNegative = trend !== undefined && trend < 0;
  const good = invertTrend ? trendNegative : trendPositive;
  const bad = invertTrend ? trendPositive : trendNegative;

  const toneRing: Record<string, string> = {
    default: "bg-primary/10 text-primary",
    success: "bg-success/15 text-success",
    warning: "bg-warning/20 text-warning-foreground",
    danger: "bg-destructive/10 text-destructive",
    info: "bg-info/15 text-info",
  };

  return (
    <div className="card-elevated group relative overflow-hidden p-5 transition-all hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 font-display text-2xl font-semibold tracking-tight text-foreground tabular-nums">
            {value}
          </p>
          {sublabel && (
            <p className="mt-1 text-xs text-muted-foreground">{sublabel}</p>
          )}
        </div>
        {Icon && (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", toneRing[tone])}>
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div className="mt-3 flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs font-medium tabular-nums",
              good && "bg-success/15 text-success",
              bad && "bg-destructive/10 text-destructive",
              !good && !bad && "bg-muted text-muted-foreground",
            )}
          >
            {trendPositive ? <ArrowUpRight className="h-3 w-3" /> : trendNegative ? <ArrowDownRight className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
            {Math.abs(trend * 100).toFixed(1)}%
          </span>
          <span className="text-xs text-muted-foreground">vs last month</span>
        </div>
      )}
    </div>
  );
}
