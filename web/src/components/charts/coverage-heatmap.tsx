"use client";

import { DIMENSION_LABELS } from "@/lib/api";

interface CoverageProps {
  rows: Array<{ name: string; by_dimension: Record<string, number> }>;
}

const DIM_ORDER = [
  "cost_economics",
  "grid_access",
  "subsidies_incentives",
  "utility_standards",
  "public_comment",
  "unknown_unknowns",
];

function cellColor(count: number, max: number): string {
  if (count === 0) return "hsl(var(--muted))";
  const t = Math.min(1, count / Math.max(1, max));
  // interpolate from muted to primary
  const alpha = 0.2 + 0.7 * t;
  return `hsl(239 84% 67% / ${alpha})`;
}

export function CoverageHeatmap({ rows }: CoverageProps) {
  if (!rows.length) {
    return <div className="text-sm text-muted-foreground">No state data.</div>;
  }
  const max = rows.reduce((m, r) => {
    for (const k of DIM_ORDER) m = Math.max(m, r.by_dimension[k] ?? 0);
    return m;
  }, 1);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="text-left text-xs font-medium text-muted-foreground py-2 pr-4"></th>
            {DIM_ORDER.map((d) => (
              <th
                key={d}
                className="text-left text-xs font-medium text-muted-foreground py-2 px-2 whitespace-nowrap"
              >
                {DIMENSION_LABELS[d]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <td className="py-1 pr-4 text-sm font-medium whitespace-nowrap">{r.name}</td>
              {DIM_ORDER.map((d) => {
                const count = r.by_dimension[d] ?? 0;
                return (
                  <td key={d} className="p-1">
                    <div
                      className="h-10 rounded-md flex items-center justify-center text-xs font-mono tabular-nums border border-border/30"
                      style={{
                        background: cellColor(count, max),
                        color: count > 0 ? "white" : "hsl(var(--muted-foreground))",
                      }}
                      title={`${r.name} · ${DIMENSION_LABELS[d]} · ${count} docs`}
                    >
                      {count}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
