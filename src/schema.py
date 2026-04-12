"""
Canonical schema for country solar intelligence data.

Every country KB file conforms to this schema. Validation is enforced
before any data enters the RAG system. This is how we guarantee
zero-hallucination grounding.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# -- Core data types --

@dataclass(frozen=True)
class Source:
    """Provenance for a single data point. REQUIRED for all facts."""
    organization: str          # e.g. "CRE", "ANEEL", "MEMR"
    document: str              # e.g. "Resolution RES/2024/003"
    url: str                   # must be a real URL
    accessed: str              # ISO date "2026-04-11"

    def validate(self) -> None:
        if not self.organization or not self.document:
            raise ValueError("organization and document required")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"invalid url: {self.url}")
        if len(self.accessed) != 10 or self.accessed[4] != "-":
            raise ValueError(f"accessed must be ISO date: {self.accessed}")


@dataclass(frozen=True)
class Document:
    """A single retrievable fact with full provenance."""
    id: str
    dimension: str                 # one of config.DIMENSIONS
    scope: str                     # "national" or specific state/province name
    content: str                   # the fact, stated clearly in prose
    sources: tuple[Source, ...]    # at least one source required
    confidence: str                # "high" | "medium" | "low"
    last_verified: str             # ISO date
    data_points: dict[str, Any] = field(default_factory=dict)
    # data_points holds structured numerics used in charts/scoring.
    # e.g. {"capex_usd_per_kw": 950, "currency": "USD"}

    def validate(self) -> None:
        if self.confidence not in ("high", "medium", "low"):
            raise ValueError(f"invalid confidence: {self.confidence}")
        if not self.sources:
            raise ValueError(f"doc {self.id} has no sources")
        for s in self.sources:
            s.validate()


@dataclass(frozen=True)
class StateMetrics:
    """Structured numerics for visualizations + scoring.

    All fields optional: use None when data not verified. The system
    reports 'data not available' rather than imputing.
    """
    # Cost & Economics
    capex_utility_usd_per_kw: float | None = None
    capex_rooftop_usd_per_kw: float | None = None
    om_usd_per_kw_year: float | None = None
    lcoe_usd_per_mwh: float | None = None
    retail_tariff_usd_per_kwh: float | None = None

    # Grid Access
    interconnection_months_avg: float | None = None
    grid_congestion: str | None = None  # "low" | "moderate" | "high"
    curtailment_risk: str | None = None

    # Resource
    ghi_kwh_m2_day: float | None = None  # solar irradiance
    capacity_factor_pct: float | None = None

    # Subsidies
    net_metering: bool | None = None
    accelerated_depreciation: bool | None = None
    import_duty_exempt: bool | None = None

    # Utility Standards
    renewable_target_pct: float | None = None
    rec_mechanism: bool | None = None

    # Installed capacity
    installed_distributed_solar_mw: float | None = None


@dataclass(frozen=True)
class StateProfile:
    """Per-state/province data container."""
    name: str
    iso_code: str | None           # e.g. "BR-MG" for Minas Gerais
    metrics: StateMetrics
    documents: tuple[Document, ...]
    data_completeness_pct: float   # 0..100, computed from filled metrics


@dataclass(frozen=True)
class CountryProfile:
    """Complete country-level knowledge base."""
    name: str
    iso_code: str                  # "BR", "MX", "ID", etc.
    currency: str                  # "BRL", "MXN", "IDR"
    exchange_rate_to_usd: float
    regulator: str                 # e.g. "ANEEL", "CRE", "MEMR"
    grid_operator: str             # e.g. "ONS", "CENACE", "PLN"
    national_documents: tuple[Document, ...]
    states: tuple[StateProfile, ...]
    last_updated: str
    coverage_summary: dict[str, Any]  # what's collected vs missing
    data_audit: dict[str, list[str]]  # {"collected": [...], "gaps": [...], "impact": [...]}


# -- Validation + (de)serialization helpers --

def validate_country(profile: CountryProfile) -> list[str]:
    """Validate a country profile. Returns list of errors (empty if valid)."""
    errors: list[str] = []
    if not profile.name or not profile.iso_code:
        errors.append(f"country missing name/iso_code")
    for d in profile.national_documents:
        try:
            d.validate()
        except ValueError as e:
            errors.append(f"national doc {d.id}: {e}")
    for s in profile.states:
        for d in s.documents:
            try:
                d.validate()
            except ValueError as e:
                errors.append(f"state {s.name} doc {d.id}: {e}")
    return errors


def compute_completeness(metrics: StateMetrics) -> float:
    """Return % of metric fields that are filled (non-None)."""
    values = asdict(metrics).values()
    filled = sum(1 for v in values if v is not None)
    total = len(list(asdict(metrics).values()))
    return round(100.0 * filled / total, 1) if total else 0.0


def document_to_dict(doc: Document) -> dict[str, Any]:
    """Serialize document for JSON/ChromaDB storage."""
    return {
        "id": doc.id,
        "dimension": doc.dimension,
        "scope": doc.scope,
        "content": doc.content,
        "confidence": doc.confidence,
        "last_verified": doc.last_verified,
        "sources": [asdict(s) for s in doc.sources],
        "data_points": doc.data_points,
    }
