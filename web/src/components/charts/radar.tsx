"use client";

import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
} from "recharts";
import { DIMENSION_LABELS } from "@/lib/api";
import type { FeasibilityScoreOut } from "@/lib/types";

export function DimensionRadar({ score }: { score: FeasibilityScoreOut }) {
  const data = score.dimension_scores.map((d) => ({
    dimension: DIMENSION_LABELS[d.dimension] ?? d.dimension,
    score: Math.round(d.score),
    imputed: d.imputed,
  }));

  return (
    <ResponsiveContainer width="100%" height={360}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="hsl(var(--border))" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
          stroke="hsl(var(--border))"
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.5rem",
            fontSize: 12,
          }}
          formatter={(value, _n, item) => {
            const p = (item as { payload?: { imputed: boolean } }).payload;
            return [`${value}${p?.imputed ? " · imputed" : ""}`, "Score"];
          }}
        />
        <Radar
          name={score.state}
          dataKey="score"
          stroke="hsl(var(--primary))"
          fill="hsl(var(--primary))"
          fillOpacity={0.28}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
