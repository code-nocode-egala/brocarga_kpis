## Goals

1. Fix the **Customer Segmentation Matrix** (scatter chart appears blank/broken).
2. Replace generic mock customer names with the real Brocarga customer list.
3. Rescale the mock dataset to realistic Brocarga economics:
   - ~€200K revenue per week in 2026
   - ~175 orders per week
   - Gross margin band 16%–24% (low-margin industry)

## Changes

### 1. `src/lib/mock-data.ts` — regenerate dataset

- Replace `CUSTOMERS` array with:
  Dyness Europe B.V., CTS International, H.M. Verploegen, ACE Filters Europe, CP Benelux Logistics B.V., Wiltec B.V., Meridian Connect, Brandmerchandising B.V., Sarens Nv, E Plus Logistics B.V., Barry Callebaut Belgium B.V.
- Change generator from "640 random invoices over 18 months" to a **week-driven generator**:
  - Loop across weeks from Jan 2025 → today (July 2026), ~80 weeks total.
  - Per week: generate ~175 invoices (jitter 160–190) with total revenue ≈ €200K (jitter ±10%).
  - Distribute revenue across customers using a weighted split (Barry Callebaut / Sarens larger, smaller clients smaller) so per-invoice values feel realistic (~€1.1K avg).
  - Margin % drawn from **16%–24%** uniform.
  - Keep Finqle share (~55%), payment terms, status logic, overdue mechanics as-is.
  - Drop multi-currency randomness — force EUR (industry is EU-based); keeps type but simplifies.
- Result: ~14K invoices; annual 2026 revenue ≈ €10.4M, matching the "200K/week" brief. Existing KPI cards (Open Invoice ~4.7M etc.) will rescale naturally.

### 2. `src/components/dashboard/CustomerTab.tsx` — fix scatter matrix

Diagnosis: with the new small customer set (11 customers) and low-variance data, all points may still render, but the current chart has two rendering risks that cause a blank chart in some viewports:
- `ZAxis range={[60, 600]}` with `dataKey="z"` (raw revenue in €) — Recharts scales bubble area against the data domain; when all `z` values are similar, bubbles can compute to 0 px. Change to a fixed size via `<Scatter shape="circle">` with an explicit radius derived from revenue, OR set `ZAxis range={[80, 400]}` and ensure a proper numeric domain.
- ScatterChart inside a flex container without a fixed pixel height on the direct parent — `h-[440px]` is on the outer ChartCard, but the ResponsiveContainer's parent is the ChartCard's inner content area which may be `flex-1` without min-height. Add `min-h-[380px]` (or explicit height) to the ResponsiveContainer wrapper.

Fixes:
- Wrap `<ResponsiveContainer>` in a `<div className="h-[380px] w-full">` so it always has a resolved height.
- Simplify bubble sizing: keep ZAxis but clamp `z` in the mapped data to a sane range (e.g. `Math.max(50, Math.min(500, revenue/2000))`) instead of raw revenue.
- Verify `scatter` array is non-empty (log-guard removed once confirmed).
- Keep quadrant reference lines, colors, tooltip unchanged.

### 3. No changes to filters, KPI logic, other tabs

All downstream aggregations (`customerInsights`, `receivablesKpis`, performance charts) consume `INVOICES` and will automatically reflect the new scale and names — no code changes needed there.

## Out of scope

- No changes to filter bar, export, theming, or routing.
- No changes to Finqle split logic (already done previously).

## Verification

After build: open Customer Insights tab, confirm scatter renders with 11 labeled bubbles, quadrant lines visible, tooltip works. Check Performance tab totals roughly match ~€200K/week * weeks-in-period.
