import { useMemo } from "react";
import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { ChartCard } from "@/components/dashboard/ChartCard";
import type { MatrixPoint, RevenueMarginMatrix as Matrix } from "@/lib/api-types";
import { fmtCompact, fmtCurrency, fmtPct } from "@/lib/format";

type QuadrantKey = "key" | "volume" | "growth" | "review";

/** Same colour language as the customer segmentation matrix: green best, red worst. */
const QUADRANTS: Record<QuadrantKey, { label: string; desc: string; fill: string; dot: string }> = {
  key: {
    label: "High revenue · High margin",
    desc: "Key accounts — protect",
    fill: "var(--color-success)",
    dot: "bg-success",
  },
  volume: {
    label: "High revenue · Low margin",
    desc: "Volume drivers — reprice",
    fill: "var(--color-chart-3)",
    dot: "bg-chart-3",
  },
  growth: {
    label: "Low revenue · High margin",
    desc: "Growth potential — expand",
    fill: "var(--color-chart-1)",
    dot: "bg-chart-1",
  },
  review: {
    label: "Low revenue · Low margin",
    desc: "Review or deprioritise",
    fill: "var(--color-destructive)",
    dot: "bg-destructive",
  },
};
const ORDER: QuadrantKey[] = ["key", "volume", "growth", "review"];

function quadrantOf(p: MatrixPoint, b: Matrix["benchmarks"]): QuadrantKey {
  const highRevenue = p.revenue >= b.revenue;
  const highMargin = p.marginPct >= b.marginPct;
  if (highRevenue) return highMargin ? "key" : "volume";
  return highMargin ? "growth" : "review";
}

/** Powers of ten spanning the data, so the log axis reads €100, €1K, €10K… */
function logTicks(points: MatrixPoint[]): number[] {
  if (!points.length) return [1, 10];
  const revenues = points.map((p) => p.revenue);
  const lo = Math.floor(Math.log10(Math.min(...revenues)));
  const hi = Math.ceil(Math.log10(Math.max(...revenues)));
  return Array.from({ length: Math.max(hi - lo, 1) + 1 }, (_, i) => 10 ** (lo + i));
}

/**
 * Revenue vs margin % per customer, split into four quadrants at the median
 * customer revenue and the portfolio's weighted margin %. Revenue is on a log
 * axis: a handful of large accounts would otherwise squash everyone else
 * against the left edge.
 */
export function RevenueMarginMatrix({ matrix }: { matrix: Matrix }) {
  const { points, benchmarks } = matrix;

  const data = useMemo(
    () => points.map((p) => ({ ...p, quadrant: quadrantOf(p, benchmarks) })),
    [points, benchmarks],
  );
  const counts = useMemo(() => {
    const c: Record<QuadrantKey, number> = { key: 0, volume: 0, growth: 0, review: 0 };
    for (const p of data) c[p.quadrant] += 1;
    return c;
  }, [data]);
  const ticks = useMemo(() => logTicks(points), [points]);
  const hasLoss = points.some((p) => p.marginPct < 0);
  const axisTick = { fontSize: 11, fill: "var(--color-muted-foreground)" };

  return (
    <ChartCard
      title="Revenue vs Margin Matrix"
      subtitle={`One dot per customer · split at median revenue (${fmtCompact(benchmarks.revenue)}) and portfolio margin (${fmtPct(benchmarks.marginPct)}) · revenue on log scale`}
    >
      {points.length === 0 ? (
        <div className="flex h-[360px] items-center justify-center text-sm text-muted-foreground">
          No customer revenue in this selection.
        </div>
      ) : (
        <div className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 12, right: 24, left: 8, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                type="number"
                dataKey="revenue"
                name="Revenue"
                scale="log"
                domain={[ticks[0], ticks[ticks.length - 1]]}
                ticks={ticks}
                allowDataOverflow
                tickFormatter={(v) => fmtCompact(v as number)}
                tick={axisTick}
                label={{
                  value: "Revenue",
                  position: "insideBottom",
                  offset: -10,
                  fill: "var(--color-muted-foreground)",
                  fontSize: 11,
                }}
              />
              <YAxis
                type="number"
                dataKey="marginPct"
                name="Margin %"
                tickFormatter={(v) => fmtPct(v as number, 0)}
                tick={axisTick}
                label={{
                  value: "Margin %",
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--color-muted-foreground)",
                  fontSize: 11,
                }}
              />
              <ZAxis range={[70, 70]} />
              {hasLoss && <ReferenceLine y={0} stroke="var(--color-border)" />}
              <ReferenceLine
                x={benchmarks.revenue}
                stroke="var(--color-muted-foreground)"
                strokeDasharray="4 4"
              />
              <ReferenceLine
                y={benchmarks.marginPct}
                stroke="var(--color-muted-foreground)"
                strokeDasharray="4 4"
              />
              <Tooltip content={<MatrixTT />} cursor={{ strokeDasharray: "3 3" }} />
              <Scatter data={data} fillOpacity={0.8} stroke="var(--color-card)" strokeWidth={1.5}>
                {data.map((p) => (
                  <Cell key={p.customer} fill={QUADRANTS[p.quadrant].fill} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        {ORDER.map((k) => (
          <div
            key={k}
            className="flex items-start gap-2 rounded-md border border-border/60 bg-muted/30 p-2"
          >
            <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${QUADRANTS[k].dot}`} />
            <div className="min-w-0 flex-1">
              <div className="flex justify-between gap-2 text-xs font-medium">
                <span>{QUADRANTS[k].label}</span>
                <span className="tabular-nums">{counts[k]}</span>
              </div>
              <div className="text-[11px] text-muted-foreground">{QUADRANTS[k].desc}</div>
            </div>
          </div>
        ))}
      </div>
    </ChartCard>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function MatrixTT({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as MatrixPoint & { quadrant: QuadrantKey };
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium">{p.customer}</div>
      <div className="mb-1 flex items-center gap-1.5 text-muted-foreground">
        <span className={`h-2 w-2 rounded-full ${QUADRANTS[p.quadrant].dot}`} />
        {QUADRANTS[p.quadrant].desc}
      </div>
      <div className="grid gap-0.5 text-muted-foreground">
        <div>
          Revenue: <span className="font-medium text-foreground">{fmtCurrency(p.revenue)}</span>
        </div>
        <div>
          Margin: <span className="font-medium text-foreground">{fmtCurrency(p.margin)}</span>
        </div>
        <div>
          Margin %: <span className="font-medium text-foreground">{fmtPct(p.marginPct)}</span>
        </div>
        <div>
          Shipments: <span className="font-medium text-foreground">{p.shipments}</span>
        </div>
      </div>
    </div>
  );
}
