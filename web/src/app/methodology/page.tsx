import { Cpu, Database, ShieldCheck, Sparkles, Languages } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const DIMENSIONS = [
  { key: "cost_economics", label: "Cost & Economics", weight: "25%", desc: "CAPEX, O&M, LCOE, retail tariffs. Normalized across currencies using quarterly FX." },
  { key: "grid_access", label: "Grid Access", weight: "20%", desc: "Interconnection queue months, congestion, curtailment risk, net-metering." },
  { key: "subsidies_incentives", label: "Subsidies & Incentives", weight: "20%", desc: "Accelerated depreciation, import duty exemptions, REC mechanisms, RE targets." },
  { key: "utility_standards", label: "Utility Standards", weight: "15%", desc: "Interconnection standards, metering requirements, code-of-grid adherence." },
  { key: "public_comment", label: "Public Comment", weight: "10%", desc: "Regulatory transparency, stakeholder engagement, rule-making cadence." },
  { key: "unknown_unknowns", label: "Unknown Unknowns", weight: "10%", desc: "Residual risk — permitting delays, political shifts, uncollected data." },
];

export default function MethodologyPage() {
  return (
    <div className="space-y-10">
      <header>
        <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Methodology</div>
        <h1 className="text-4xl font-semibold tracking-tight mt-1">How we score markets</h1>
        <p className="mt-4 text-muted-foreground max-w-3xl leading-relaxed">
          PowerTrust scores are grounded in verified policy and market documents. Every fact is traceable to a regulator,
          grid operator, or peer-reviewed source — with translations disclosed where applicable.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Scoring dimensions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted-foreground">
                <th className="text-left py-2 pr-4 font-medium">Dimension</th>
                <th className="text-left py-2 pr-4 font-medium">Weight</th>
                <th className="text-left py-2 font-medium">What it measures</th>
              </tr>
            </thead>
            <tbody>
              {DIMENSIONS.map((d) => (
                <tr key={d.key} className="border-t border-border/40 align-top">
                  <td className="py-3 pr-4 font-medium whitespace-nowrap">{d.label}</td>
                  <td className="py-3 pr-4 tabular-nums text-primary">{d.weight}</td>
                  <td className="py-3 text-muted-foreground leading-relaxed">{d.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InfoCard
          icon={Database}
          title="Verified sources"
          body="Every data point cites a regulator, grid operator, or peer-reviewed source. No synthetic data enters the knowledge base."
        />
        <InfoCard
          icon={Cpu}
          title="HPC validation"
          body="High-Performance Corroboration (HPC) cross-checks facts against multiple independent sources. Rejected facts are tracked in the audit log."
        />
        <InfoCard
          icon={ShieldCheck}
          title="Zero hallucination"
          body="Chat answers are grounded strictly in retrieved documents. When data is missing, the system says so — it never invents numbers."
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Languages className="h-4 w-4 text-primary" />
            Translation & provenance
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground leading-relaxed space-y-2">
          <p>
            Many source documents are in Portuguese, Spanish, Bahasa, Vietnamese, or Malay. We retrieve in the source
            language and disclose the original on every translated fact.
          </p>
          <p>
            Exchange rates are refreshed quarterly against the USD, and all monetary values are normalized for
            cross-market comparison.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ratings</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <tbody>
              {[
                ["Excellent", "80 – 100", "emerald"],
                ["Good", "65 – 79", "lime"],
                ["Moderate", "50 – 64", "amber"],
                ["Challenging", "35 – 49", "orange"],
                ["Poor", "0 – 34", "rose"],
              ].map(([label, range, color]) => (
                <tr key={label} className="border-b border-border/40 last:border-0">
                  <td className="py-2.5 pr-4">
                    <span className={`inline-flex items-center gap-2 text-sm text-${color}-400`}>
                      <span className={`h-1.5 w-1.5 rounded-full bg-${color}-400`} />
                      {label}
                    </span>
                  </td>
                  <td className="py-2.5 tabular-nums text-muted-foreground">{range}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function InfoCard({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5">
      <div className="flex items-center gap-2 text-primary">
        <Icon className="h-4 w-4" />
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{body}</p>
    </div>
  );
}
