"""
Knowledge Base loader.

Loads country JSON files, validates against schema, and produces
CountryProfile objects. Immutable — never mutates loaded data.
"""
from __future__ import annotations

import json
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
    """Flatten all documents (national + state) for indexing."""
    docs = list(profile.national_documents)
    for state in profile.states:
        docs.extend(state.documents)
    return docs
