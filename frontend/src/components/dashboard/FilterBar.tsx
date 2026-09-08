import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Filter, RotateCcw, Calendar } from "lucide-react";
import { useMeta } from "@/lib/api";
import { DEFAULT_DEAL_STATUS, type PeriodPreset } from "@/lib/api-types";

export type { PeriodPreset };

export interface Filters {
  period: PeriodPreset;
  from: string; // ISO date (inclusive)
  to: string;   // ISO date (inclusive)
  broker: string;
  customer: string;
  /** Invoice state: Open / Overdue / Paid / ..., or "all". */
  status: string;
  /** Bubble's `Status` on the deal, or "all". */
  dealStatus: string;
}

function shift(iso: string, fn: (d: Date) => void): string {
  const d = new Date(iso);
  fn(d);
  return d.toISOString().slice(0, 10);
}

/** The client clock, used only until /api/meta/ reports the dataset's own date. */
function browserToday(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Resolve a named period into an inclusive [from, to] range.
 *
 * `today` is passed in rather than read from the clock: the backend anchors all
 * overdue maths to `Dataset.as_of`, and the date pickers must agree with it or
 * a preset would select a range the API then interprets differently. This is
 * the display-side twin of `range_for_preset` in `apps.domain.filters`.
 */
export function rangeForPreset(
  preset: PeriodPreset,
  today: string,
  current?: { from: string; to: string },
): { from: string; to: string } {
  const to = today;
  switch (preset) {
    case "day":     return { from: to, to };
    case "week":    return { from: shift(to, (d) => d.setDate(d.getDate() - 7)), to };
    case "4weeks":  return { from: shift(to, (d) => d.setDate(d.getDate() - 28)), to };
    case "month":   return { from: shift(to, (d) => d.setMonth(d.getMonth() - 1)), to };
    case "quarter": return { from: shift(to, (d) => d.setMonth(d.getMonth() - 3)), to };
    case "year":    return { from: shift(to, (d) => d.setFullYear(d.getFullYear() - 1)), to };
    case "all":     return { from: "1970-01-01", to };
    case "custom":  return current ?? { from: shift(to, (d) => d.setMonth(d.getMonth() - 1)), to };
    default:        return current ?? { from: shift(to, (d) => d.setMonth(d.getMonth() - 1)), to };
  }
}

/**
 * Opening filter state for a given reference date: the trailing year, with
 * every filter open except the deal status.
 *
 * That one opens on completed business rather than on "all", matching the
 * backend default -- an unfiltered dashboard counting cancelled deals as
 * revenue would be wrong, not merely broad.
 */
export function defaultFilters(today: string, dealStatus = DEFAULT_DEAL_STATUS): Filters {
  const r = rangeForPreset("year", today);
  return {
    period: "year",
    from: r.from,
    to: r.to,
    broker: "all",
    customer: "all",
    status: "all",
    dealStatus,
  };
}

/**
 * Initial state for the first render, before /api/meta/ has answered. Anchored
 * to the browser date; Reset re-anchors to the dataset date once it is known.
 */
export const DEFAULT_FILTERS: Filters = defaultFilters(browserToday());

interface FilterBarProps {
  filters: Filters;
  onChange: (f: Filters) => void;
}

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const { data: meta } = useMeta();
  // Empty until the API answers — an empty dataset has no reference date, so
  // the pickers fall back to the client clock rather than clamping to "".
  const today = meta.asOf || browserToday();

  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    onChange({ ...filters, [key]: value });

  const onPresetChange = (v: string) => {
    const preset = v as PeriodPreset;
    if (preset === "custom") {
      onChange({ ...filters, period: "custom" });
    } else {
      const r = rangeForPreset(preset, today);
      onChange({ ...filters, period: preset, from: r.from, to: r.to });
    }
  };

  // Re-anchors to the dataset's own date and to whichever deal status the
  // backend treats as the default, rather than to this file's constant.
  const onReset = () => onChange(defaultFilters(today, meta.defaultDealStatus || undefined));

  const onDateChange = (key: "from" | "to", value: string) => {
    onChange({ ...filters, period: "custom", [key]: value });
  };

  // A filter still selected after its option disappeared from the dataset would
  // leave the Select blank; listing it keeps the trigger honest until reset.
  const brokerOptions = withSelected(meta.brokers, filters.broker);
  const customerOptions = withSelected(meta.customers, filters.customer);
  const dealStatusOptions = withSelected(meta.dealStatuses, filters.dealStatus);

  return (
    <div className="card-elevated flex flex-wrap items-center gap-2 p-3">
      <div className="mr-1 flex items-center gap-2 pl-1 text-xs font-medium text-muted-foreground">
        <Filter className="h-3.5 w-3.5" />
        Filters
      </div>

      <FilterSelect label="Period" value={filters.period} onChange={onPresetChange}
        options={[
          { v: "day", l: "Today" },
          { v: "week", l: "Last 7 days" },
          { v: "4weeks", l: "Last 4 weeks" },
          { v: "month", l: "Last 30 days" },
          { v: "quarter", l: "Last quarter" },
          { v: "year", l: "Last year" },
          { v: "all", l: "All time" },
          { v: "custom", l: "Custom range" },
        ]}
      />

      <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-2 h-9">
        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="date"
          value={filters.from}
          max={filters.to}
          onChange={(e) => onDateChange("from", e.target.value)}
          className="bg-transparent text-xs font-medium outline-none tabular-nums"
        />
        <span className="text-xs text-muted-foreground">→</span>
        <input
          type="date"
          value={filters.to}
          min={filters.from}
          max={today}
          onChange={(e) => onDateChange("to", e.target.value)}
          className="bg-transparent text-xs font-medium outline-none tabular-nums"
        />
      </div>

      <FilterSelect label="Broker" value={filters.broker} onChange={(v) => set("broker", v)}
        options={[{ v: "all", l: "All brokers" }, ...brokerOptions.map((b) => ({ v: b, l: b }))]}
      />
      <FilterSelect label="Customer" value={filters.customer} onChange={(v) => set("customer", v)}
        options={[{ v: "all", l: "All customers" }, ...customerOptions.map((c) => ({ v: c, l: c }))]}
      />
      <FilterSelect label="Deal" value={filters.dealStatus} onChange={(v) => set("dealStatus", v)}
        options={[
          { v: "all", l: "All deal statuses" },
          ...dealStatusOptions.map((s) => ({ v: s, l: s })),
        ]}
      />
      <FilterSelect label="Invoice" value={filters.status} onChange={(v) => set("status", v)}
        options={[
          { v: "all", l: "All statuses" },
          ...meta.statuses.map((s) => ({ v: s, l: s })),
        ]}
      />

      <div className="ml-auto">
        <Button size="sm" variant="ghost" onClick={onReset} className="gap-1.5">
          <RotateCcw className="h-3.5 w-3.5" /> Reset
        </Button>
      </div>
    </div>
  );
}

function withSelected(options: string[], selected: string): string[] {
  if (selected === "all" || options.includes(selected)) return options;
  return [...options, selected];
}

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { v: string; l: string }[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-9 min-w-[140px] gap-1.5 border-border bg-background text-xs font-medium">
        <span className="text-muted-foreground">{label}:</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="max-h-72">
        {options.map((o) => (
          <SelectItem key={o.v} value={o.v} className="text-xs">
            {o.l}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
