/**
 * The only place this app talks to the network.
 *
 * All requests are same-origin `/api/*`: in development webpack-dev-server
 * proxies that prefix to Django on :8000, and in production Django serves both
 * the bundle and the API. Nothing here knows about Bubble — credentials never
 * reach the browser.
 *
 * Every hook returns a payload that is *always* renderable: on a pending or
 * failed request the caller gets the matching EMPTY_* constant rather than
 * `undefined`, so a tab never has to guard each field it reads. The query state
 * is exposed alongside it (`isPending` / `isError`) for the status pill in the
 * header, not for branching the whole tab into a placeholder.
 *
 * There is exactly one dashboard request. `/api/dashboard/` carries all three
 * tabs, and `usePerformance` / `useReceivables` / `useCustomers` are `select`s
 * over that single query rather than three fetches of their own.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { Filters } from "@/components/dashboard/FilterBar";
import {
  EMPTY_CUSTOMERS,
  EMPTY_DASHBOARD,
  EMPTY_META,
  EMPTY_PERFORMANCE,
  EMPTY_PORTFOLIO,
  EMPTY_RECEIVABLES,
  type CustomersPayload,
  type DashboardPayload,
  type MetaResponse,
  type PerformancePayload,
  type PortfolioPayload,
  type ReceivablesPayload,
} from "./api-types";

const API_BASE = "/api";

/** Thrown for any non-2xx response so react-query treats it as a failure. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly url: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string, search?: URLSearchParams): Promise<T> {
  const url = search ? `${API_BASE}${path}?${search}` : `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });

  if (!res.ok) {
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, url);
  }
  return (await res.json()) as T;
}

/**
 * Filters as query parameters.
 *
 * These names are the contract `apps.api.params.parse_filters` reads:
 * `from`/`to` are inclusive ISO dates; `broker`, `customer` and `dealStatus`
 * repeat once per selected value; and `period` carries the preset the user
 * picked so the backend can log or re-resolve it.
 *
 * No `broker` or `customer` sent means every one. `dealStatus` is different:
 * the backend reads its absence as the default status, so an empty selection
 * is sent explicitly as "all".
 *
 * `status` (the invoice state) is deliberately not sent. The filter bar no
 * longer offers it, and `parse_filters` reads an absent `status` as "all", so
 * omitting it is what leaves invoices unfiltered -- sending "all" explicitly
 * would mean the same thing but imply a control that no longer exists.
 */
export function filterParams(f: Filters): URLSearchParams {
  const params = new URLSearchParams({ from: f.from, to: f.to, period: f.period });
  for (const b of f.brokers) params.append("broker", b);
  for (const c of f.customers) params.append("customer", c);
  for (const s of f.dealStatuses.length ? f.dealStatuses : ["all"]) params.append("dealStatus", s);
  if (f.viewer) params.set("viewer", f.viewer);
  return params;
}

/**
 * Stable cache key for a filter set. Mirrors `Filters.cache_key_part` on the
 * backend so both sides invalidate on the same boundaries -- minus the invoice
 * status, which this app no longer varies: the backend still has that field
 * and still includes it in its own key, but every request from here leaves it
 * at "all", so it can never be the thing that distinguishes two filter sets.
 */
function filterKey(f: Filters): string {
  const list = (values: string[]) => [...values].sort().join(",") || "all";
  return [f.viewer ?? "", f.from, f.to, list(f.brokers), list(f.customers), list(f.dealStatuses)].join("|");
}

/** URL of the full CSV extract — a plain link/navigation, not a fetch. */
export function transactionsExportUrl(f: Filters): string {
  return `${API_BASE}/transactions/export/?${filterParams(f)}`;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** What a tab gets: never-undefined data plus the raw query for status. */
export interface Loaded<T> {
  data: T;
  query: UseQueryResult<T, Error>;
}

/**
 * Filter-bar options and the dataset reference date.
 *
 * Cached longer than the dashboards: the customer and broker lists change on
 * the timescale of onboarding, not of clicking a filter.
 */
export function useMeta(viewer?: string): Loaded<MetaResponse> {
  const query = useQuery<MetaResponse, Error>({
    queryKey: ["meta", viewer ?? ""],
    queryFn: () =>
      getJson<MetaResponse>("/meta/", viewer ? new URLSearchParams({ viewer }) : undefined),
    staleTime: 5 * 60_000,
  });
  return { data: query.data ?? EMPTY_META, query };
}

/**
 * The one dashboard request: all three tabs for the current filter set.
 *
 * The tabs are never looking at different filters — there is a single filter
 * bar above all of them — so asking for them separately bought nothing and
 * cost three round trips over the same Bubble snapshot. Fetching them together
 * also means an unopened tab is already populated: Radix unmounts inactive tab
 * content, and when it mounts, its hook reads this cache entry instead of
 * starting a request.
 */
export function useDashboard(filters: Filters): Loaded<DashboardPayload> {
  return useDashboardSlice(filters, selectAll, EMPTY_DASHBOARD);
}

/**
 * One tab's slice of the dashboard response.
 *
 * Every caller shares the query key, so react-query dedupes them to a single
 * fetch and a single cache entry; only the `select` differs. The selectors are
 * module-level constants rather than inline arrows so their identity is stable
 * and react-query can skip re-running them on every render.
 */
function useDashboardSlice<T>(
  filters: Filters,
  select: (payload: DashboardPayload) => T,
  fallback: T,
): Loaded<T> {
  const query = useQuery<DashboardPayload, Error, T>({
    queryKey: ["dashboard", filterKey(filters)],
    queryFn: () => getJson<DashboardPayload>("/dashboard/", filterParams(filters)),
    select,
    // Keeps the previous filter set's numbers on screen while the next one
    // loads, so the charts do not collapse to zero and back on every change.
    placeholderData: (prev) => prev,
  });
  return { data: query.data ?? fallback, query };
}

const selectAll = (payload: DashboardPayload): DashboardPayload => payload;
const selectPerformance = (payload: DashboardPayload) => payload.performance;
const selectReceivables = (payload: DashboardPayload) => payload.receivables;
const selectCustomers = (payload: DashboardPayload) => payload.customers;

export function usePerformance(filters: Filters): Loaded<PerformancePayload> {
  return useDashboardSlice(filters, selectPerformance, EMPTY_PERFORMANCE);
}

export function useReceivables(filters: Filters): Loaded<ReceivablesPayload> {
  return useDashboardSlice(filters, selectReceivables, EMPTY_RECEIVABLES);
}

/** Broker KPIs portfolio tab. Its own request: the cockpit's combined payload does not carry it. */
export function usePortfolio(filters: Filters): Loaded<PortfolioPayload> {
  const query = useQuery<PortfolioPayload, Error>({
    queryKey: ["portfolio", filterKey(filters)],
    queryFn: () => getJson<PortfolioPayload>("/dashboard/portfolio/", filterParams(filters)),
    placeholderData: (prev) => prev,
  });
  return { data: query.data ?? EMPTY_PORTFOLIO, query };
}

export function useCustomers(filters: Filters): Loaded<CustomersPayload> {
  return useDashboardSlice(filters, selectCustomers, EMPTY_CUSTOMERS);
}
