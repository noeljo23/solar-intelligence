import Link from "next/link";
import { ArrowUpRight, TrendingUp, Target, Database, BarChart3 } from "lucide-react";
import { api } from "@/lib/api";
import { CountryHeader } from "@/components/country-header";
import { RatingBadge } from "@/components/rating-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FeasibilityBar } from "@/components/charts/feasibility-bar";
import { MetricBar } from "@/components/charts/metric-bar";
import { CountryCompare } from "@/components/charts/country-compare";
import type { Rating } from "@/lib/types";

function countryRating(score: number): Rating {
  if (score >= 80) return "Excellent";
  if (score >= 65) return "Good";
  if (score >= 50) return "Moderate";
  if (score >= 35) return "Challenging";
  return "Poor";
}

function recommendation(rating: Rating, topState: string, gaps: number): string {
  if (rating === "Excellent" || rating === "Good") {
    return `Shortlist ${topState} for a 25–50 MW pilot. Verify interconnection queue timing before committing capex.`;
  }
  if (rating === "Moderate") {
    return `Opportunistic. Close ${gaps} data gaps first, then re-evaluate ${topState} with a local partner.`;
  }
  return `Hold. Wait for updated regulator data or HPC re-run; score reflects real policy and data risk.`;
}

export default async function DashboardPage({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  const [profile, scores, countries] = await Promise.all([
    api.country(name),
    api.scores(name),
    api.countries(),
  ]);

  const avg =
    scores.length > 0
      ? scores.reduce((s, x) => s + x.total_score, 0) / scores.length
      : 0;
  const rating = countryRating(avg);
  const top = scores.length
    ? scores.reduce((a, b) => (a.total_score > b.total_score ? a : b))
    : null;
  const totalDocs =
    profile.national_documents.length +
    profile.states.reduce((s, st) => s + st.documents.length, 0);
  const gaps = profile.data_audit.gaps?.length ?? 0;

  const metricRows = profile.states.map((s) => ({
    state: s.name,
    ...s.metrics,
  }));

  return (
    <div>
      <CountryHeader profile={profile} />

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
        <KpiTile
          label="Feasibility"
          value={avg.toFixed(0)}
          sub={<RatingBadge rating={rating} />}
          icon={TrendingUp}
        />
        <KpiTile
          label="Top state"
          value={top?.state ?? "—"}
          sub={<span className="text-muted-foreground">{top ? `${top.total_score.toFixed(0)}/100` : ""}</span>}
          icon={Target}
        />
        <KpiTile label="States scored" value={scores.length} icon={BarChart3} />
        <KpiTile label="Documents" value={totalDocs} icon={Database} />
      </section>

      <Tabs defaultValue="ranking" className="space-y-6">
        <TabsList>
          <TabsTrigger value="ranking">Ranking</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="compare">Compare</TabsTrigger>
        </TabsList>

        <TabsContent value="ranking">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle>Feasibility by state</CardTitle>
              </CardHeader>
              <CardContent>
                <FeasibilityBar scores={scores} />
              </CardContent>
            </Card>
            <Card className="lg:col-span-2 bg-gradient-to-br from-primary/5 via-card/40 to-secondary/5">
              <CardHeader>
                <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground font-medium">
                  Recommendation
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <p className="text-base leading-relaxed">{recommendation(rating, top?.state ?? "—", gaps)}</p>
                {top && (
                  <Link
                    href={`/country/${encodeURIComponent(name)}/deep-dive?state=${encodeURIComponent(top.state)}`}
                    className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                  >
                    Drill into {top.state}
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="metrics">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <MetricBar
              rows={metricRows}
              metric="capex_utility_usd_per_kw"
              title="CAPEX — utility-scale"
              unit="USD/kW"
            />
            <MetricBar
              rows={metricRows}
              metric="interconnection_months_avg"
              title="Grid interconnection"
              unit="months"
            />
            <MetricBar
              rows={metricRows}
              metric="retail_tariff_usd_per_kwh"
              title="Retail tariff"
              unit="USD/kWh"
            />
            <MetricBar
              rows={metricRows}
              metric="ghi_kwh_m2_day"
              title="Solar irradiance"
              unit="kWh/m²/day"
            />
          </div>
        </TabsContent>

        <TabsContent value="compare">
          <Card>
            <CardHeader>
              <CardTitle>Market feasibility across countries</CardTitle>
            </CardHeader>
            <CardContent>
              <CountryCompare countries={countries} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function KpiTile({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  sub?: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums truncate">{value}</div>
      {sub && <div className="mt-1.5 text-xs">{sub}</div>}
    </div>
  );
}
