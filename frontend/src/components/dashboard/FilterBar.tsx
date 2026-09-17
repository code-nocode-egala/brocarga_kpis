import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Check, ChevronDown, Filter, RotateCcw, Calendar, Search } from "lucide-react";
import { useMeta } from "@/lib/api";
import { DEFAULT_DEAL_STATUS, type PeriodPreset } from "@/lib/api-types";

export type { PeriodPreset };

export interface Filters {
  period: PeriodPreset;
  from: string; // ISO date (inclusive)
  to: string;   // ISO date (inclusive)
  /** Selected broker names; empty means every broker. */
  brokers: string[];
  /** Selected customer names; empty means every customer. */
  customers: string[];
  /** Bubble's `Status` values on the deal; empty means every status. */
  dealStatuses: string[];
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
 * Opening filter state for a given reference date: all time, with every
 * filter open except the deal status.
 *
 * That one opens on completed business rather than on "all", matching the
 * backend default -- an unfiltered dashboard counting cancelled deals as
 * revenue would be wrong, not merely broad.
 */
export function defaultFilters(today: string, dealStatus = DEFAULT_DEAL_STATUS): Filters {
  const r = rangeForPreset("all", today);
  return {
    period: "all",
    from: r.from,
    to: r.to,
    brokers: [],
    customers: [],
    dealStatuses: [dealStatus],
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
  /** Hides the deal-status filter; its value in `filters` is still applied. */
  showDealStatus?: boolean;
}

export function FilterBar({ filters, onChange, showDealStatus = true }: FilterBarProps) {
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

  // A value still selected after its option disappeared from the dataset could
  // not be unticked; listing it keeps the selection visible until reset.
  const brokerOptions = withSelected(meta.brokers, filters.brokers);
  const customerOptions = withSelected(meta.customers, filters.customers);
  const dealStatusOptions = withSelected(meta.dealStatuses, filters.dealStatuses);

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

      <FilterMultiSelect label="Broker" allLabel="All brokers" values={filters.brokers}
        onChange={(v) => set("brokers", v)} options={brokerOptions}
      />
      <FilterMultiSelect label="Customer" allLabel="All customers" values={filters.customers}
        onChange={(v) => set("customers", v)} options={customerOptions} searchable
      />
      {showDealStatus && (
        <FilterMultiSelect label="Deal" allLabel="All deal statuses" values={filters.dealStatuses}
          onChange={(v) => set("dealStatuses", v)} options={dealStatusOptions}
        />
      )}

      <div className="ml-auto">
        <Button size="sm" variant="ghost" onClick={onReset} className="gap-1.5">
          <RotateCcw className="h-3.5 w-3.5" /> Reset
        </Button>
      </div>
    </div>
  );
}

function withSelected(options: string[], selected: string[]): string[] {
  return [...options, ...selected.filter((s) => !options.includes(s))];
}

/**
 * Checkbox list in a popover. An empty selection means "all", so clearing the
 * last checkbox or picking "All" both return to the unfiltered state.
 */
function FilterMultiSelect({ label, allLabel, values, onChange, options, searchable }: {
  label: string; allLabel: string; values: string[]; onChange: (v: string[]) => void; options: string[];
  /** Adds a search box; for lists too long to scroll through. */
  searchable?: boolean;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const visible = q ? options.filter((o) => o.toLowerCase().includes(q)) : options;
  const toggle = (o: string) =>
    onChange(values.includes(o) ? values.filter((v) => v !== o) : [...values, o]);
  const summary =
    values.length === 0 ? allLabel : values.length === 1 ? values[0] : `${values.length} selected: ${values.join(", ")}`;

  return (
    <Popover onOpenChange={(open) => !open && setQuery("")}>
      <PopoverTrigger asChild>
        <button
          type="button"
          title={values.length > 1 ? values.join(", ") : undefined}
          className="flex h-9 w-full min-w-[140px] cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-border bg-background px-3 py-2 text-xs font-medium shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <span className="text-muted-foreground">{label}:</span>
          <span className="truncate">{summary}</span>
          <ChevronDown className="ml-auto h-4 w-4 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className={`${searchable ? "w-80" : "w-60"} p-1`}>
        {searchable && (
          <div className="flex items-center gap-2 border-b border-border px-2 pb-1">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search…"
              className="h-8 w-full bg-transparent text-xs outline-none placeholder:text-muted-foreground"
            />
          </div>
        )}
        <div className="max-h-72 overflow-auto">
          {!q && (
            <>
              <MultiOption label={allLabel} checked={values.length === 0} onSelect={() => onChange([])} />
              <div className="my-1 h-px bg-border" />
            </>
          )}
          {visible.map((o) => (
            <MultiOption key={o} label={o} checked={values.includes(o)} onSelect={() => toggle(o)} />
          ))}
          {visible.length === 0 && <div className="px-2 py-3 text-center text-xs text-muted-foreground">No matches</div>}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function MultiOption({ label, checked, onSelect }: { label: string; checked: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      role="menuitemcheckbox"
      aria-checked={checked}
      onClick={onSelect}
      className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-xs hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none"
    >
      <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border ${checked ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>
        {checked && <Check className="h-3 w-3" />}
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
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
