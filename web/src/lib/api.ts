import type {
  AuditOut,
  ChatResponseOut,
  CountryProfileOut,
  CountrySummary,
  FeasibilityScoreOut,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  countries: () => get<CountrySummary[]>("/api/countries"),
  country: (name: string) =>
    get<CountryProfileOut>(`/api/country/${encodeURIComponent(name)}`),
  scores: (name: string) =>
    get<FeasibilityScoreOut[]>(`/api/country/${encodeURIComponent(name)}/scores`),
  audit: (name: string) =>
    get<AuditOut>(`/api/country/${encodeURIComponent(name)}/audit`),
  dimensions: () => get<Array<{ key: string; label: string }>>("/api/dimensions"),
  chat: async (
    country: string,
    message: string,
    history: Array<{ role: string; content: string }>,
  ): Promise<ChatResponseOut> => {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country, message, history }),
    });
    if (!res.ok) throw new Error(`chat ${res.status}`);
    return res.json();
  },
};

export const DIMENSION_LABELS: Record<string, string> = {
  cost_economics: "Cost & Economics",
  grid_access: "Grid Access",
  subsidies_incentives: "Subsidies",
  utility_standards: "Utility Standards",
  public_comment: "Public Comment",
  unknown_unknowns: "Unknown Unknowns",
};

export const RATING_TONE: Record<string, { bg: string; text: string; ring: string }> = {
  Excellent:   { bg: "bg-emerald-500/10", text: "text-emerald-400", ring: "ring-emerald-500/30" },
  Good:        { bg: "bg-lime-500/10",    text: "text-lime-400",    ring: "ring-lime-500/30"    },
  Moderate:    { bg: "bg-amber-500/10",   text: "text-amber-400",   ring: "ring-amber-500/30"   },
  Challenging: { bg: "bg-orange-500/10",  text: "text-orange-400",  ring: "ring-orange-500/30"  },
  Poor:        { bg: "bg-rose-500/10",    text: "text-rose-400",    ring: "ring-rose-500/30"    },
};

export const RATING_COLOR: Record<string, string> = {
  Excellent:   "#22C55E",
  Good:        "#84CC16",
  Moderate:    "#F59E0B",
  Challenging: "#F97316",
  Poor:        "#EF4444",
};
