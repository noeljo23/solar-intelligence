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
import type { CountrySummary } from "@/lib/types";

export function CountryCompare({ countries }: { countries: CountrySummary[] }) {
  const data = countries
    .filter((c) => c.avg_score != null)
    .map((c) => ({
      country: c.name,
      score: c.avg_score as number,
      states: c.states_scored,
      completeness: c.completeness,
    }))
    .sort((a, b) => a.score - b.score);

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, 36 * data.length)}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 48, left: 16, bottom: 8 }}>
        <XAxis type="number" domain={[0, 108]} hide />
        <YAxis
          type="category"
          dataKey="country"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          width={100}
        />
        <Tooltip
          cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.5rem",
            fontSize: 12,
          }}
          formatter={(v, _n, item) => {
            const p = (item as { payload?: { states: number; completeness: number } }).payload;
            const n = typeof v === "number" ? v : Number(v);
            return [`${n.toFixed(1)}${p ? ` · ${p.states} states · ${p.completeness}%` : ""}`, "Score"];
          }}
        />
        <Bar dataKey="score" fill="hsl(var(--secondary))" radius={[4, 4, 4, 4]} barSize={20}>
          <LabelList
            dataKey="score"
            position="right"
            style={{ fill: "hsl(var(--foreground))", fontSize: 11, fontWeight: 600 }}
            formatter={(v) => (typeof v === "number" ? v.toFixed(0) : String(v ?? ""))}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
