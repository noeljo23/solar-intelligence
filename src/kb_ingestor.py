"""
HPC-collected data -> Knowledge Base ingestor.

Reads JSONL output from `hpc.run_collection` (accepted facts + synthesis +
audit report) and merges it into the existing country_*.json knowledge base.

Design principles:
  - Additive: never overwrite hand-curated seed documents. Deduplicate by
    (dimension, scope, content-prefix) so re-running is idempotent.
  - Provenance-preserving: every ingested fact becomes a Document with its
    full source triple (organization, document, url) and an accessed date.
  - Audit-aware: corroboration + citation + consistency metrics are attached
    to coverage_summary under a 'hpc_audit' namespace so the dashboard can
    surface them.
  - Fail-closed on schema mismatch: if a JSONL row is malformed it is
    skipped with a log line, not coerced.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# Filename is "{Country}_{STATE_OR_NATIONAL}_{dimension}.jsonl".
# Country may contain underscores (e.g. South_Africa), so we split from the right.
# Dimension is one of a known set; the middle chunk is scope.
_KNOWN_DIMENSIONS = {
    "cost_economics",
    "grid_access",
    "subsidies_incentives",
    "utility_standards",
    "public_comment",
    "unknown_unknowns",
}

# Map common country filename conventions to the exact KB country name.
_COUNTRY_FILE_MAP = {
    "Brazil": "Brazil",
    "Mexico": "Mexico",
    "Indonesia": "Indonesia",
    "Vietnam": "Vietnam",
    "South_Africa": "South Africa",
}


@dataclass(frozen=True)
class CollectedRun:
    """Parsed contents of one collected JSONL file."""
    country: str
    scope: str                         # "national" or state/province name
    dimension: str
    accepted: list[dict[str, Any]]     # each = {"fact": CandidateFact dict, "verdict": ...}
    rejected: list[dict[str, Any]]
    synthesis: dict[str, Any] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


def parse_filename(filename: str) -> tuple[str, str, str] | None:
    """Return (country_kb_name, scope, dimension) or None if unrecognized."""
    stem = filename[:-6] if filename.endswith(".jsonl") else filename
    # Pull dimension off the right
    for dim in _KNOWN_DIMENSIONS:
        suffix = f"_{dim}"
        if stem.endswith(suffix):
            rest = stem[: -len(suffix)]
            break
    else:
        return None
    # Pull scope off the right
    if "_" not in rest:
        return None
    country_raw, scope_raw = rest.rsplit("_", 1) if rest.endswith("NATIONAL") else _split_country_scope(rest)
    country_kb = _COUNTRY_FILE_MAP.get(country_raw.replace(" ", "_"), country_raw.replace("_", " "))
    scope = "national" if scope_raw == "NATIONAL" else scope_raw.replace("_", " ")
    return country_kb, scope, dim


def _split_country_scope(rest: str) -> tuple[str, str]:
    """Split {Country}_{State} where Country may have internal underscores.

    Strategy: try longest-matching known country prefix; fall back to single split.
    """
    for country in sorted(_COUNTRY_FILE_MAP.keys(), key=len, reverse=True):
        prefix = f"{country}_"
        if rest.startswith(prefix):
            return country, rest[len(prefix):]
    # Fallback: assume last underscore separates country from state.
    return rest.rsplit("_", 1) if "_" in rest else (rest, "")


def parse_collected_file(path: Path) -> CollectedRun | None:
    """Parse a single collected JSONL file. Skips unrecognized filenames."""
    parsed = parse_filename(path.name)
    if parsed is None:
        print(f"[ingestor] skip unrecognized filename: {path.name}")
        return None
    country, scope, dimension = parsed

    accepted: list[dict] = []
    rejected: list[dict] = []
    synthesis: dict = {}
    audit: dict = {}

    if path.stat().st_size == 0:
        return CollectedRun(country, scope, dimension, accepted, rejected, synthesis, audit)

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[ingestor] {path.name}:{line_no} JSON decode error: {e}")
                continue
            status = row.get("status")
            if status == "accepted":
                accepted.append(row)
            elif status == "rejected":
                rejected.append(row)
            elif status == "synthesis":
                synthesis = row.get("synthesis", {})
            elif status == "audit":
                audit = row.get("audit", {})

    return CollectedRun(country, scope, dimension, accepted, rejected, synthesis, audit)


def _slug(text: str, maxlen: int = 40) -> str:
    """Short alnum slug of text for doc IDs."""
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return s[:maxlen] or "UNKNOWN"


def _country_code(country: str) -> str:
    codes = {
        "Brazil": "BR", "Mexico": "MX", "Indonesia": "ID",
        "Vietnam": "VN", "South Africa": "ZA",
    }
    return codes.get(country, _slug(country, 3))


def build_documents(run: CollectedRun) -> list[dict[str, Any]]:
    """Convert accepted facts in a CollectedRun into KB Document dicts."""
    today = date.today().isoformat()
    country_code = _country_code(run.country)
    scope_tag = "NAT" if run.scope == "national" else _slug(run.scope, 8)
    dim_tag = _slug(run.dimension, 8)

    # audit.corroboration_count is indexed aligned to accepted-facts order (1-based).
    corroboration = run.audit.get("corroboration_count") or []

    docs: list[dict[str, Any]] = []
    for i, row in enumerate(run.accepted, start=1):
        fact_data = row.get("fact") or {}
        verdict = row.get("verdict") or {}
        content = str(fact_data.get("fact", "")).strip()
        if not content:
            continue

        confidence_raw = str(verdict.get("confidence", "medium")).lower()
        confidence = confidence_raw if confidence_raw in ("high", "medium", "low") else "medium"

        source = {
            "organization": str(fact_data.get("source_organization", "unknown")),
            "document": str(fact_data.get("source_document", "unknown")),
            "url": str(fact_data.get("source_url", "")),
            "accessed": today,
        }
        if not source["url"].startswith(("http://", "https://")):
            continue  # schema requires valid URL

        data_points = fact_data.get("data_points") or {}
        if not isinstance(data_points, dict):
            data_points = {}

        # Attach HPC audit provenance to data_points so it reaches the dashboard.
        corr_count = corroboration[i - 1] if i - 1 < len(corroboration) else 1
        data_points = {
            **data_points,
            "_hpc": {
                "corroboration_count": corr_count,
                "corroborated": bool(corr_count >= 2),
                "fact_index": i,
            },
        }

        doc_id = f"{country_code}_{scope_tag}_{dim_tag}_HPC_{i:03d}"
        docs.append({
            "id": doc_id,
            "dimension": run.dimension,
            "scope": run.scope,
            "content": content,
            "sources": [source],
            "confidence": confidence,
            "last_verified": today,
            "data_points": data_points,
        })
    return docs


def _dedup_key(doc: dict[str, Any]) -> tuple[str, str, str]:
    """Stable key for deduplication: (dimension, scope, content-prefix)."""
    return (
        str(doc.get("dimension", "")),
        str(doc.get("scope", "")),
        str(doc.get("content", ""))[:160].lower(),
    )


def merge_run_into_country(country_doc: dict[str, Any], run: CollectedRun) -> dict[str, Any]:
    """Return a NEW country dict with run merged in. Never mutates input."""
    new_docs = build_documents(run)
    if not new_docs:
        return country_doc

    # Build lookup of existing docs keyed by (dim, scope, content) to avoid duplicates.
    existing_keys: set[tuple[str, str, str]] = set()
    for d in country_doc.get("national_documents", []):
        existing_keys.add(_dedup_key(d))
    for s in country_doc.get("states", []):
        for d in s.get("documents", []):
            existing_keys.add(_dedup_key(d))

    added_national: list[dict] = []
    per_state_additions: dict[str, list[dict]] = {}
    for d in new_docs:
        if _dedup_key(d) in existing_keys:
            continue
        if d["scope"] == "national":
            added_national.append(d)
        else:
            per_state_additions.setdefault(d["scope"], []).append(d)

    if not added_national and not per_state_additions and not run.synthesis and not run.audit:
        return country_doc

    # Build new national_documents tuple.
    new_national = list(country_doc.get("national_documents", [])) + added_national

    # Merge state-level docs into existing states; create shell states for new names.
    new_states: list[dict] = []
    seen_state_names: set[str] = set()
    for s in country_doc.get("states", []):
        name = s.get("name")
        seen_state_names.add(name)
        additions = per_state_additions.get(name, [])
        if not additions:
            new_states.append(s)
            continue
        new_s = {**s, "documents": list(s.get("documents", [])) + additions}
        new_states.append(new_s)
    for name, additions in per_state_additions.items():
        if name in seen_state_names:
            continue
        new_states.append({
            "name": name,
            "iso_code": None,
            "metrics": {},
            "documents": additions,
            "data_completeness_pct": 0.0,
        })

    # Append audit summary into coverage_summary under hpc_audit key.
    hpc_audit = dict(country_doc.get("coverage_summary", {}).get("hpc_audit", {}))
    dim_entry = {
        "scope": run.scope,
        "accepted": len(run.accepted),
        "rejected": len(run.rejected),
        "corroborated_count": sum(
            1 for c in (run.audit.get("corroboration_count") or []) if c >= 2
        ),
        "unsupported_sentences": len(run.audit.get("unsupported_sentence_indices") or []),
        "consistency_min": (min(run.audit.get("consistency_support") or [0])
                            if run.audit.get("consistency_support") else 0),
        "synthesis_chars": len(str(run.synthesis.get("content", ""))),
        "issues": list(run.audit.get("issues") or []),
    }
    key = f"{run.scope}::{run.dimension}"
    hpc_audit[key] = dim_entry
    new_coverage = {**country_doc.get("coverage_summary", {}), "hpc_audit": hpc_audit}

    return {
        **country_doc,
        "national_documents": new_national,
        "states": new_states,
        "coverage_summary": new_coverage,
        "last_updated": date.today().isoformat(),
    }


@dataclass(frozen=True)
class IngestReport:
    files_read: int
    files_skipped: int
    countries_updated: list[str]
    docs_added: int
    dims_audited: int


def ingest_directory(
    collected_dir: Path,
    kb_dir: Path,
    dry_run: bool = False,
) -> IngestReport:
    """Ingest every *.jsonl in collected_dir into the matching country KB file."""
    if not collected_dir.exists():
        raise FileNotFoundError(collected_dir)
    if not kb_dir.exists():
        raise FileNotFoundError(kb_dir)

    # Group runs by country so each country file is written once.
    by_country: dict[str, list[CollectedRun]] = {}
    files_read = files_skipped = 0
    for path in sorted(collected_dir.glob("*.jsonl")):
        files_read += 1
        run = parse_collected_file(path)
        if run is None or (not run.accepted and not run.synthesis and not run.audit):
            files_skipped += 1
            continue
        by_country.setdefault(run.country, []).append(run)

    countries_updated: list[str] = []
    docs_added = 0
    dims_audited = 0

    for country, runs in by_country.items():
        safe_name = country.replace(" ", "_")
        country_path = kb_dir / f"country_{safe_name}.json"
        if not country_path.exists():
            print(f"[ingestor] skip {country}: no KB file at {country_path.name}")
            continue
        with open(country_path, "r", encoding="utf-8") as f:
            country_doc = json.load(f)
        before_count = _count_docs(country_doc)
        for run in runs:
            country_doc = merge_run_into_country(country_doc, run)
            dims_audited += 1 if run.audit else 0
        after_count = _count_docs(country_doc)
        delta = after_count - before_count
        docs_added += delta
        countries_updated.append(country)
        if not dry_run:
            with open(country_path, "w", encoding="utf-8") as f:
                json.dump(country_doc, f, indent=2, ensure_ascii=False)
        print(f"[ingestor] {country}: +{delta} docs, {len(runs)} runs ingested")

    return IngestReport(
        files_read=files_read,
        files_skipped=files_skipped,
        countries_updated=countries_updated,
        docs_added=docs_added,
        dims_audited=dims_audited,
    )


def _count_docs(country_doc: dict[str, Any]) -> int:
    n = len(country_doc.get("national_documents", []))
    for s in country_doc.get("states", []):
        n += len(s.get("documents", []))
    return n


def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Ingest HPC-collected JSONL into KB")
    parser.add_argument("--collected", type=Path, required=True, help="Directory of *.jsonl files")
    parser.add_argument("--kb-dir", type=Path, required=True, help="Knowledge base directory")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    args = parser.parse_args()
    report = ingest_directory(args.collected, args.kb_dir, dry_run=args.dry_run)
    print(f"\nfiles_read={report.files_read}  skipped={report.files_skipped}")
    print(f"countries_updated={report.countries_updated}")
    print(f"docs_added={report.docs_added}  dims_audited={report.dims_audited}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
