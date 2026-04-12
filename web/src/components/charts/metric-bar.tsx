"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LabelList,
} from "recharts";

export function MetricBar({
  rows,
  metric,
  title,
  unit,
}: {
  rows: Array<Record<string, unknown>>;
  metric: string;
  title: string;
  unit?: string;
}) {
  const data = rows
    .filter((r) => r[metric] != null)
    .map((r) => ({ state: r.state as string, value: r[metric] as number }))
    .sort((a, b) => b.value - a.value);

  if (!data.length) {
    return (
      <div className="rounded-xl border border-border/60 bg-card/40 p-6 text-sm text-muted-foreground">
        <div className="font-medium text-foreground mb-2">{title}</div>
        No verified data for this metric.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <div className="flex items-baseline justify-between mb-3 px-2">
        <div className="text-sm font-medium">{title}</div>
        {unit && <div className="text-xs text-muted-foreground">{unit}</div>}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 8 }}>
          <XAxis
            dataKey="state"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
          />
          <YAxis
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
              fontSize: 12,
            }}
          />
          <Bar dataKey="value" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} barSize={28}>
            <LabelList
              dataKey="value"
              position="top"
              style={{ fill: "hsl(var(--foreground))", fontSize: 10, fontWeight: 600 }}
              formatter={(v) => (typeof v === "number" ? v.toFixed(1) : String(v ?? ""))}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
