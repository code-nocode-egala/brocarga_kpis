import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import { BrokerKpisApp } from "./BrokerKpisApp";
import { ErrorBoundary } from "./components/ErrorBoundary";

import "./styles.css";

// Every number on screen comes through here: the hooks in src/lib/api.ts are
// the app's only data source. `retry: 1` keeps a dead backend from hammering
// the network — the tabs render their empty payloads and the header says the
// API is unreachable rather than the page failing.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
});

// Two pages, one bundle: Django and the dev server both answer every non-API
// path with the same index.html, so the path alone decides which page renders.
const path = window.location.pathname.replace(/\/+$/, "");
const Page = path === "/broker_kpis" ? BrokerKpisApp : App;

const container = document.getElementById("root");

if (!container) {
  throw new Error('Root container "#root" was not found in the document.');
}

createRoot(container).render(
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <Page />
    </QueryClientProvider>
  </ErrorBoundary>,
);
