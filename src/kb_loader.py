"""
Knowledge Base loader.

Loads country JSON files, validates against schema, and produces
CountryProfile objects. Immutable — never mutates loaded data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.schema import (
    CountryProfile,
    Document,
    Source,
    StateMetrics,
    StateProfile,
    compute_completeness,
    validate_country,
)

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def _source_from_dict(d: dict) -> Source:
    return Source(
        organization=d["organization"],
        document=d["document"],
        url=d["url"],
        accessed=d["accessed"],
    )


def _document_from_dict(d: dict) -> Document:
    return Document(
        id=d["id"],
        dimension=d["dimension"],
        scope=d["scope"],
        content=d["content"],
        sources=tuple(_source_from_dict(s) for s in d["sources"]),
        confidence=d["confidence"],
        last_verified=d["last_verified"],
        data_points=d.get("data_points", {}),
    )


def _metrics_from_dict(d: dict) -> StateMetrics:
    return StateMetrics(**{k: v for k, v in d.items() if v is not None or True})


def _state_from_dict(d: dict) -> StateProfile:
    metrics = _metrics_from_dict(d.get("metrics", {}))
    docs = tuple(_document_from_dict(x) for x in d.get("documents", []))
    return StateProfile(
        name=d["name"],
        iso_code=d.get("iso_code"),
        metrics=metrics,
        documents=docs,
        data_completeness_pct=compute_completeness(metrics),
    )


def load_country(path: Path) -> CountryProfile:
    """Load and validate a single country KB JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    national_docs = tuple(_document_from_dict(x) for x in raw.get("national_documents", []))
    states = tuple(_state_from_dict(s) for s in raw.get("states", []))

    profile = CountryProfile(
        name=raw["name"],
        iso_code=raw["iso_code"],
        currency=raw["currency"],
        exchange_rate_to_usd=float(raw["exchange_rate_to_usd"]),
        regulator=raw["regulator"],
        grid_operator=raw["grid_operator"],
        national_documents=national_docs,
        states=states,
        last_updated=raw["last_updated"],
        coverage_summary=raw.get("coverage_summary", {}),
        data_audit=raw.get("data_audit", {"collected": [], "gaps": [], "impact": []}),
    )

    errors = validate_country(profile)
    if errors:
        raise ValueError(f"validation errors in {path.name}: {errors[:3]}")

    return profile


def load_all_countries(kb_dir: Path) -> dict[str, CountryProfile]:
    """Load every country_*.json in kb_dir. Returns name -> profile."""
    if not kb_dir.exists():
        return {}
    profiles: dict[str, CountryProfile] = {}
    for path in sorted(kb_dir.glob("country_*.json")):
        try:
            profile = load_country(path)
            profiles[profile.name] = profile
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            # Log and skip invalid files — never silently succeed with bad data
            print(f"[kb_loader] SKIPPED {path.name}: {e}")
    return profiles


def iter_all_documents(profile: CountryProfile) -> list[Document]:
    """Flatten all documents (national + state) for indexing.

    Also synthesizes retrievable docs from per-state StateMetrics so chat
    can answer questions about numeric fields that would otherwise only be
    visible to the scoring layer.
    """
    docs = list(profile.national_documents)
    for state in profile.states:
        docs.extend(state.documents)
    docs.extend(_synthesize_metric_documents(profile))
    return docs


def _slug(name: str) -> str:
    return _SLUG_RE.sub("_", name).strip("_").upper()


def _pick_fallback_sources(
    profile: CountryProfile, dimension: str
) -> tuple[Source, ...] | None:
    """Borrow sources from an existing doc in the same dimension so synthesized
    metric docs carry real provenance. Prefers state-level, then national."""
    for state in profile.states:
        for d in state.documents:
            if d.dimension == dimension and d.sources:
                return d.sources
    for d in profile.national_documents:
        if d.dimension == dimension and d.sources:
            return d.sources
    return None


def _synthesize_metric_documents(profile: CountryProfile) -> list[Document]:
    """Emit per-state docs summarizing StateMetrics so retrieval can surface
    numeric fields (capex, tariff, interconnection, GHI, etc.) that would
    otherwise live only in the scoring layer."""
    cost_sources = _pick_fallback_sources(profile, "cost_economics")
    grid_sources = _pick_fallback_sources(profile, "grid_access")
    synthesized: list[Document] = []

    for state in profile.states:
        m = state.metrics
        state_tag = f"{state.name} ({profile.name})"

        cost_bits: list[str] = []
        cost_dp: dict[str, float] = {}
        if m.capex_utility_usd_per_kw is not None:
            cost_bits.append(f"utility-scale CAPEX USD {m.capex_utility_usd_per_kw:.0f}/kW")
            cost_dp["capex_utility_usd_per_kw"] = m.capex_utility_usd_per_kw
        if m.capex_rooftop_usd_per_kw is not None:
            cost_bits.append(f"rooftop CAPEX USD {m.capex_rooftop_usd_per_kw:.0f}/kW")
            cost_dp["capex_rooftop_usd_per_kw"] = m.capex_rooftop_usd_per_kw
        if m.lcoe_usd_per_mwh is not None:
            cost_bits.append(f"LCOE USD {m.lcoe_usd_per_mwh:.0f}/MWh")
            cost_dp["lcoe_usd_per_mwh"] = m.lcoe_usd_per_mwh
        if m.retail_tariff_usd_per_kwh is not None:
            cost_bits.append(f"retail tariff USD {m.retail_tariff_usd_per_kwh:.3f}/kWh")
            cost_dp["retail_tariff_usd_per_kwh"] = m.retail_tariff_usd_per_kwh
        if m.ghi_kwh_m2_day is not None:
            cost_bits.append(f"GHI {m.ghi_kwh_m2_day:.2f} kWh/m^2/day")
            cost_dp["ghi_kwh_m2_day"] = m.ghi_kwh_m2_day
        if cost_bits and cost_sources:
            synthesized.append(Document(
                id=f"{profile.iso_code}_{_slug(state.name)}_METRICS_COST",
                dimension="cost_economics",
                scope=state.name,
                content=f"{state_tag} solar economics — " + "; ".join(cost_bits) + ".",
                sources=cost_sources,
                confidence="medium",
                last_verified=profile.last_updated,
                data_points=cost_dp,
            ))

        grid_bits: list[str] = []
        grid_dp: dict[str, float | str] = {}
        if m.interconnection_months_avg is not None:
            grid_bits.append(f"avg interconnection {m.interconnection_months_avg:.1f} months")
            grid_dp["interconnection_months_avg"] = m.interconnection_months_avg
        if m.grid_congestion:
            grid_bits.append(f"grid congestion {m.grid_congestion}")
            grid_dp["grid_congestion"] = m.grid_congestion
        if m.curtailment_risk:
            grid_bits.append(f"curtailment risk {m.curtailment_risk}")
            grid_dp["curtailment_risk"] = m.curtailment_risk
        if m.installed_distributed_solar_mw is not None:
            grid_bits.append(f"installed distributed solar {m.installed_distributed_solar_mw:.0f} MW")
            grid_dp["installed_distributed_solar_mw"] = m.installed_distributed_solar_mw
        if grid_bits and grid_sources:
            synthesized.append(Document(
                id=f"{profile.iso_code}_{_slug(state.name)}_METRICS_GRID",
                dimension="grid_access",
                scope=state.name,
                content=f"{state_tag} grid profile — " + "; ".join(grid_bits) + ".",
                sources=grid_sources,
                confidence="medium",
                last_verified=profile.last_updated,
                data_points=grid_dp,
            ))

    return synthesized
