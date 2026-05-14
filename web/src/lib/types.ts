export type Rating = "Excellent" | "Good" | "Moderate" | "Challenging" | "Poor";

export interface CountrySummary {
  name: string;
  iso_code: string;
  regulator: string;
  avg_score: number | null;
  rating: Rating | null;
  states_scored: number;
  documents: number;
  completeness: number;
}

export interface SourceDoc {
  organization: string;
  document: string;
  url: string;
  accessed: string;
}

export interface DocumentOut {
  id: string;
  dimension: string;
  scope: string;
  content: string;
  confidence: "high" | "medium" | "low";
  last_verified: string;
  sources: SourceDoc[];
  data_points: Record<string, unknown>;
  is_hpc: boolean;
}

export interface StateMetrics {
  capex_utility_usd_per_kw: number | null;
  capex_rooftop_usd_per_kw: number | null;
  om_usd_per_kw_year: number | null;
  lcoe_usd_per_mwh: number | null;
  retail_tariff_usd_per_kwh: number | null;
  interconnection_months_avg: number | null;
  grid_congestion: string | null;
  curtailment_risk: string | null;
  ghi_kwh_m2_day: number | null;
  capacity_factor_pct: number | null;
  net_metering: boolean | null;
  accelerated_depreciation: boolean | null;
  import_duty_exempt: boolean | null;
  renewable_target_pct: number | null;
  rec_mechanism: boolean | null;
  installed_distributed_solar_mw: number | null;
}

export interface StateOut {
  name: string;
  iso_code: string | null;
  metrics: StateMetrics;
  documents: DocumentOut[];
  data_completeness_pct: number;
}

export interface CountryProfileOut {
  name: string;
  iso_code: string;
  currency: string;
  exchange_rate_to_usd: number;
  regulator: string;
  grid_operator: string;
  last_updated: string;
  national_documents: DocumentOut[];
  states: StateOut[];
  coverage_summary: Record<string, unknown>;
  data_audit: {
    collected?: string[];
    gaps?: string[];
    impact?: string[];
  };
}

export interface DimensionScore {
  dimension: string;
  score: number;
  inputs_used: string[];
  inputs_missing: string[];
  imputed: boolean;
}

export interface FeasibilityScoreOut {
  state: string;
  country: string;
  total_score: number;
  rating: Rating;
  dimension_scores: DimensionScore[];
  data_completeness_pct: number;
}

export interface AuditOut {
  country: string;
  states: number;
  documents_total: number;
  documents_national: number;
  documents_hpc: number;
  coverage: Array<{ name: string; by_dimension: Record<string, number> }>;
  audit: {
    collected?: string[];
    gaps?: string[];
    impact?: string[];
  };
  hpc_audit: null | {
    corroboration_rate_pct?: number;
    citation_rate_pct?: number;
    facts_rejected?: number;
  };
}

export interface ChatResponseOut {
  answer: string;
  sources: Array<Record<string, unknown>>;
}

export interface GlobalChatResponseOut {
  answer: string;
  countries_used: string[];
  sources: Array<Record<string, unknown>>;
}
