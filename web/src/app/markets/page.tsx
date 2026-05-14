import Link from "next/link";
import { api } from "@/lib/api";
import { RatingBadge } from "@/components/rating-badge";
import type { CountrySummary } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "Markets — Solis" };

export default async function MarketsPage() {
  const countries = await api.countries().catch(() => [] as CountrySummary[]);
  const sorted = [...countries].sort(
    (a, b) => (b.avg_score ?? -1) - (a.avg_score ?? -1),
  );

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-[28px] font-semibold tracking-tight">Markets</h1>
        <p className="mt-2 text-muted-foreground">
          Feasibility across {countries.length} emerging markets. Sorted by score.
        </p>
      </header>

      <div className="divide-y divide-border rounded-xl border border-border bg-card">
        {sorted.map((c) => (
          <Link
            key={c.name}
            href={`/country/${encodeURIComponent(c.name)}`}
            className="flex items-center justify-between px-5 py-4 hover:bg-muted/50 transition"
          >
            <div className="flex items-baseline gap-4">
              <span className="text-[11px] uppercase tracking-widest text-muted-foreground w-10">
                {c.iso_code}
              </span>
              <span className="text-base font-medium">{c.name}</span>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <span className="tabular-nums text-muted-foreground">
                {c.states_scored} states · {c.documents} docs
              </span>
              <span className="tabular-nums font-medium w-10 text-right">
                {c.avg_score != null ? c.avg_score.toFixed(0) : "—"}
              </span>
              <RatingBadge rating={c.rating} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
