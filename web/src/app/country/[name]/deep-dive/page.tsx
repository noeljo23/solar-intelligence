import { api, DIMENSION_LABELS } from "@/lib/api";
import { CountryHeader } from "@/components/country-header";
import { StatePicker } from "@/components/state-picker";
import { DocumentCard } from "@/components/document-card";
import { DimensionRadar } from "@/components/charts/radar";
import { RatingBadge } from "@/components/rating-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DocumentOut, StateMetrics, StateOut } from "@/lib/types";

const METRIC_LABELS: Array<{ key: keyof StateMetrics; label: string; unit?: string; digits?: number }> = [
  { key: "capex_utility_usd_per_kw", label: "CAPEX — utility", unit: "USD/kW", digits: 0 },
  { key: "capex_rooftop_usd_per_kw", label: "CAPEX — rooftop", unit: "USD/kW", digits: 0 },
  { key: "om_usd_per_kw_year", label: "O&M", unit: "USD/kW-yr", digits: 1 },
  { key: "lcoe_usd_per_mwh", label: "LCOE", unit: "USD/MWh", digits: 1 },
  { key: "retail_tariff_usd_per_kwh", label: "Retail tariff", unit: "USD/kWh", digits: 3 },
  { key: "interconnection_months_avg", label: "Interconnection", unit: "months", digits: 1 },
  { key: "grid_congestion", label: "Grid congestion" },
  { key: "curtailment_risk", label: "Curtailment risk" },
  { key: "ghi_kwh_m2_day", label: "GHI", unit: "kWh/m²/day", digits: 2 },
  { key: "capacity_factor_pct", label: "Capacity factor", unit: "%", digits: 1 },
  { key: "net_metering", label: "Net metering" },
  { key: "accelerated_depreciation", label: "Accelerated depreciation" },
  { key: "import_duty_exempt", label: "Import duty exempt" },
  { key: "renewable_target_pct", label: "Renewable target", unit: "%", digits: 0 },
  { key: "rec_mechanism", label: "REC mechanism" },
  { key: "installed_distributed_solar_mw", label: "Installed DG solar", unit: "MW", digits: 0 },
];

function formatMetric(value: unknown, digits?: number, unit?: string): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    const n = digits !== undefined ? value.toFixed(digits) : String(value);
    return unit ? `${n} ${unit}` : n;
  }
  return String(value);
}

function groupByDimension(docs: DocumentOut[]): Record<string, DocumentOut[]> {
  const map: Record<string, DocumentOut[]> = {};
  for (const d of docs) {
    (map[d.dimension] ??= []).push(d);
  }
  return map;
}

export default async function DeepDivePage({
  params,
  searchParams,
}: {
  params: { name: string };
  searchParams: { state?: string };
}) {
  const name = decodeURIComponent(params.name);
  const [profile, scores] = await Promise.all([api.country(name), api.scores(name)]);

  if (profile.states.length === 0) {
    return (
      <div>
        <CountryHeader profile={profile} />
        <div className="rounded-xl border border-border/60 bg-card/40 p-8 text-muted-foreground">
          No state-level data collected yet for {profile.name}.
        </div>
      </div>
    );
  }

  const stateNames = profile.states.map((s) => s.name);
  const selected = searchParams.state && stateNames.includes(searchParams.state)
    ? searchParams.state
    : stateNames[0];
  const state = profile.states.find((s) => s.name === selected) as StateOut;
  const score = scores.find((s) => s.state === selected);
  const stateDocs = state.documents;
  const relatedNational = profile.national_documents;
  const docsByDim = groupByDimension([...stateDocs, ...relatedNational]);

  return (
    <div>
      <CountryHeader profile={profile} />

      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground mb-1">State</div>
          <h2 className="text-2xl font-semibold tracking-tight">{state.name}</h2>
        </div>
        <StatePicker states={stateNames} current={selected} />
      </div>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <Tile label="Total score" value={score ? score.total_score.toFixed(0) : "—"} sub={score ? <RatingBadge rating={score.rating} /> : null} />
        <Tile label="Data completeness" value={`${state.data_completeness_pct.toFixed(0)}%`} />
        <Tile label="State documents" value={stateDocs.length} />
        <Tile label="National documents" value={relatedNational.length} />
      </section>

      <Tabs defaultValue="scores" className="space-y-6">
        <TabsList>
          <TabsTrigger value="scores">Scores</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="scores">
          {score ? (
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
              <Card className="lg:col-span-3">
                <CardHeader>
                  <CardTitle>Dimension profile</CardTitle>
                </CardHeader>
                <CardContent>
                  <DimensionRadar score={score} />
                </CardContent>
              </Card>
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Dimensions</CardTitle>
                </CardHeader>
                <CardContent>
                  <table className="w-full text-sm">
                    <tbody>
                      {score.dimension_scores.map((d) => (
                        <tr key={d.dimension} className="border-b border-border/40 last:border-0">
                          <td className="py-2.5 text-muted-foreground">
                            {DIMENSION_LABELS[d.dimension] ?? d.dimension}
                          </td>
                          <td className="py-2.5 text-right tabular-nums font-medium">
                            {d.score.toFixed(0)}
                            {d.imputed && (
                              <span className="ml-2 text-[10px] uppercase tracking-wider text-amber-400">
                                imputed
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="rounded-xl border border-border/60 bg-card/40 p-8 text-muted-foreground">
              No score available for this state yet.
            </div>
          )}
        </TabsContent>

        <TabsContent value="metrics">
          <Card>
            <CardHeader>
              <CardTitle>State metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
                {METRIC_LABELS.map(({ key, label, unit, digits }) => (
                  <div key={key} className="flex items-center justify-between border-b border-border/40 py-2.5 text-sm">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="tabular-nums font-medium">
                      {formatMetric(state.metrics[key], digits, unit)}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sources">
          <div className="space-y-6">
            {Object.entries(docsByDim).map(([dim, docs]) => (
              <section key={dim}>
                <div className="flex items-center gap-3 mb-3">
                  <h3 className="text-sm uppercase tracking-widest text-muted-foreground">
                    {DIMENSION_LABELS[dim] ?? dim}
                  </h3>
                  <div className="h-px bg-border/60 flex-1" />
                  <span className="text-xs text-muted-foreground">{docs.length}</span>
                </div>
                <div className="space-y-3">
                  {docs.map((d) => (
                    <DocumentCard key={d.id} doc={d} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-4">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums truncate">{value}</div>
      {sub && <div className="mt-1.5 text-xs">{sub}</div>}
    </div>
  );
}
