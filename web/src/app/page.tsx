import Link from "next/link";
import { ArrowRight, Sparkles, ShieldCheck, Zap, Globe2 } from "lucide-react";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";
import { RatingBadge } from "@/components/rating-badge";
import { Card, CardContent } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export default async function Home() {
  const countries = await api.countries().catch(() => []);
  const scored = countries.filter((c) => c.avg_score != null);
  const avg =
    scored.length > 0
      ? scored.reduce((s, c) => s + (c.avg_score ?? 0), 0) / scored.length
      : 0;
  const totalDocs = countries.reduce((s, c) => s + c.documents, 0);

  return (
    <div className="flex min-h-screen">
      <Sidebar countries={countries} activeCountry={null} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-16 space-y-16">
          <section className="space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Zero-hallucination RAG · 190+ verified sources
            </div>
            <h1 className="text-5xl sm:text-6xl font-semibold tracking-tight text-balance">
              Distributed solar intelligence,{" "}
              <span className="gradient-text">grounded in sources</span>.
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
              Feasibility scoring, policy comparison, and cited answers for 10 emerging markets
              across LatAm, Africa, and Southeast Asia. Every fact links to a regulator-verified
              document — nothing is invented.
            </p>
            <div className="flex gap-3 pt-2">
              <Link
                href={`/country/${encodeURIComponent(countries[0]?.name ?? "Mexico")}`}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90 transition"
              >
                Explore markets
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/methodology"
                className="inline-flex items-center rounded-lg border border-border bg-background/40 px-5 py-2.5 text-sm font-medium hover:bg-accent/10 transition"
              >
                How it works
              </Link>
            </div>
          </section>

          <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatTile label="Countries" value={countries.length} icon={Globe2} />
            <StatTile label="Verified docs" value={totalDocs} icon={ShieldCheck} />
            <StatTile label="Avg score" value={avg.toFixed(0)} icon={Zap} />
            <StatTile
              label="States scored"
              value={scored.reduce((s, c) => s + c.states_scored, 0)}
              icon={Sparkles}
            />
          </section>

          <section className="space-y-4">
            <div className="flex items-end justify-between">
              <h2 className="text-2xl font-semibold tracking-tight">Markets</h2>
              <p className="text-sm text-muted-foreground">Select a country to drill down</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {countries.map((c) => (
                <Link
                  key={c.name}
                  href={`/country/${encodeURIComponent(c.name)}`}
                  className="group"
                >
                  <Card className="h-full transition-all hover:border-primary/40 hover:bg-card/80 hover:shadow-lg hover:shadow-primary/5">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
                            {c.iso_code}
                          </div>
                          <div className="text-lg font-semibold group-hover:text-primary transition-colors">
                            {c.name}
                          </div>
                        </div>
                        <RatingBadge rating={c.rating} />
                      </div>
                      <div className="flex items-baseline gap-2 mb-4">
                        <div className="text-3xl font-semibold tabular-nums">
                          {c.avg_score != null ? c.avg_score.toFixed(0) : "—"}
                        </div>
                        <div className="text-xs text-muted-foreground">/ 100</div>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <MiniStat label="States" value={c.states_scored} />
                        <MiniStat label="Docs" value={c.documents} />
                        <MiniStat label="Cov" value={`${c.completeness.toFixed(0)}%`} />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function StatTile({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-xs">{label}</span>
      </div>
      <div className="mt-1.5 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-muted/40 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}
