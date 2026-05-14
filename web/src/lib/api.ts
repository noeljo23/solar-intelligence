import type {
  AuditOut,
  ChatResponseOut,
  CountryProfileOut,
  CountrySummary,
  FeasibilityScoreOut,
  GlobalChatResponseOut,
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
  chatGlobal: async (
    message: string,
    history: Array<{ role: string; content: string }>,
  ): Promise<GlobalChatResponseOut> => {
    const res = await fetch(`${API_BASE}/api/chat-global`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    if (!res.ok) throw new Error(`chat-global ${res.status}`);
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
  Excellent:   { bg: "bg-emerald-50",  text: "text-emerald-700", ring: "ring-emerald-200" },
  Good:        { bg: "bg-lime-50",     text: "text-lime-700",    ring: "ring-lime-200"    },
  Moderate:    { bg: "bg-amber-50",    text: "text-amber-700",   ring: "ring-amber-200"   },
  Challenging: { bg: "bg-orange-50",   text: "text-orange-700",  ring: "ring-orange-200"  },
  Poor:        { bg: "bg-rose-50",     text: "text-rose-700",    ring: "ring-rose-200"    },
};

export const RATING_COLOR: Record<string, string> = {
  Excellent:   "#22C55E",
  Good:        "#84CC16",
  Moderate:    "#F59E0B",
  Challenging: "#F97316",
  Poor:        "#EF4444",
};
