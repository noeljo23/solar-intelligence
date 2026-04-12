import { Building2, Zap, CalendarDays, Coins } from "lucide-react";
import type { CountryProfileOut } from "@/lib/types";

export function CountryHeader({ profile }: { profile: CountryProfileOut }) {
  const meta: Array<{ icon: React.ComponentType<{ className?: string }>; label: string; value: string }> = [
    { icon: Building2, label: "Regulator", value: profile.regulator.split("(")[0].trim() },
    { icon: Zap, label: "Grid", value: profile.grid_operator.split("(")[0].trim() },
    { icon: Coins, label: "FX", value: `${profile.currency} ${profile.exchange_rate_to_usd.toFixed(2)}/USD` },
    { icon: CalendarDays, label: "Updated", value: profile.last_updated },
  ];

  return (
    <header className="mb-8">
      <div className="flex items-baseline gap-3 mb-1.5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          {profile.iso_code}
        </div>
      </div>
      <h1 className="text-4xl font-semibold tracking-tight">{profile.name}</h1>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
        {meta.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="inline-flex items-center gap-2">
              <Icon className="h-3.5 w-3.5" />
              <span className="text-xs uppercase tracking-wider">{m.label}</span>
              <span className="text-foreground font-medium">{m.value}</span>
            </div>
          );
        })}
      </div>
    </header>
  );
}
