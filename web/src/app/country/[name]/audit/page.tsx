import { AlertTriangle, CheckCircle2, TrendingDown, Cpu } from "lucide-react";
import { api } from "@/lib/api";
import { CountryHeader } from "@/components/country-header";
import { CoverageHeatmap } from "@/components/charts/coverage-heatmap";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function AuditPage({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  const [profile, audit] = await Promise.all([api.country(name), api.audit(name)]);

  const collected = audit.audit.collected ?? [];
  const gaps = audit.audit.gaps ?? [];
  const impact = audit.audit.impact ?? [];

  return (
    <div>
      <CountryHeader profile={profile} />

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <Tile label="States" value={audit.states} />
        <Tile label="Documents" value={audit.documents_total} />
        <Tile label="National" value={audit.documents_national} />
        <Tile label="HPC-validated" value={audit.documents_hpc} icon={Cpu} />
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <AuditList
          title="Collected"
          items={collected}
          icon={CheckCircle2}
          tone="text-emerald-400"
          empty="Nothing collected yet."
        />
        <AuditList
          title="Gaps"
          items={gaps}
          icon={AlertTriangle}
          tone="text-amber-400"
          empty="No open gaps."
        />
        <AuditList
          title="Impact on decisions"
          items={impact}
          icon={TrendingDown}
          tone="text-rose-400"
          empty="No known impacts."
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Coverage by state & dimension</CardTitle>
        </CardHeader>
        <CardContent>
          <CoverageHeatmap rows={audit.coverage} />
        </CardContent>
      </Card>

      {audit.hpc_audit && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-primary" />
              HPC audit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
              <HpcStat label="Corroboration" value={audit.hpc_audit.corroboration_rate_pct} unit="%" />
              <HpcStat label="Citation rate" value={audit.hpc_audit.citation_rate_pct} unit="%" />
              <HpcStat label="Facts rejected" value={audit.hpc_audit.facts_rejected} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Tile({ label, value, icon: Icon }: { label: string; value: number | string; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function AuditList({
  title,
  items,
  icon: Icon,
  tone,
  empty,
}: {
  title: string;
  items: string[];
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
  empty: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Icon className={`h-4 w-4 ${tone}`} />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {items.map((s, i) => (
              <li key={i} className="flex gap-2.5 leading-relaxed">
                <span className={`mt-1.5 h-1 w-1 rounded-full shrink-0 ${tone.replace("text-", "bg-")}`} />
                <span className="text-foreground/90">{s}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function HpcStat({ label, value, unit }: { label: string; value: number | undefined; unit?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">
        {value !== undefined ? `${value.toFixed(unit === "%" ? 1 : 0)}${unit ?? ""}` : "—"}
      </div>
    </div>
  );
}
