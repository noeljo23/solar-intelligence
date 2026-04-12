"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  LabelList,
} from "recharts";
import { RATING_COLOR } from "@/lib/api";
import type { FeasibilityScoreOut } from "@/lib/types";

export function FeasibilityBar({ scores }: { scores: FeasibilityScoreOut[] }) {
  if (!scores.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        No scored states yet.
      </div>
    );
  }
  const data = [...scores]
    .sort((a, b) => a.total_score - b.total_score)
    .map((s) => ({
      state: s.state,
      score: Math.round(s.total_score * 10) / 10,
      rating: s.rating,
      completeness: s.data_completeness_pct,
    }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, 44 * data.length)}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 48, left: 16, bottom: 8 }}>
        <XAxis
          type="number"
          domain={[0, 108]}
          hide
        />
        <YAxis
          type="category"
          dataKey="state"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          width={110}
        />
        <Tooltip
          cursor={{ fill: "hsl(var(--muted) / 0.4)" }}
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.5rem",
            fontSize: 12,
          }}
          formatter={(value, _name, item) => {
            const p = (item as { payload?: { rating: string; completeness: number } }).payload;
            return [`${value}${p ? ` · ${p.rating}` : ""}`, "Score"];
          }}
          labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
        />
        <Bar dataKey="score" radius={[4, 4, 4, 4]} barSize={20}>
          {data.map((d) => (
            <Cell key={d.state} fill={RATING_COLOR[d.rating]} />
          ))}
          <LabelList
            dataKey="score"
            position="right"
            style={{ fill: "hsl(var(--foreground))", fontSize: 11, fontWeight: 600 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
