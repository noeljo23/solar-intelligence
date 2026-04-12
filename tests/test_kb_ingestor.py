"""Tests for src.kb_ingestor - filename parsing, doc building, merging, full ingest."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.kb_ingestor import (
    CollectedRun,
    _country_code,
    _dedup_key,
    _slug,
    build_documents,
    ingest_directory,
    merge_run_into_country,
    parse_collected_file,
    parse_filename,
)


@pytest.mark.unit
class TestSlug:
    def test_basic(self) -> None:
        assert _slug("hello world") == "HELLO_WORLD"

    def test_strips_special(self) -> None:
        assert _slug("Ley 21.118!") == "LEY_21_118"

    def test_empty(self) -> None:
        assert _slug("") == "UNKNOWN"

    def test_truncates(self) -> None:
        assert len(_slug("a" * 200, maxlen=10)) == 10


@pytest.mark.unit
class TestCountryCode:
    @pytest.mark.parametrize("country,expected", [
        ("Brazil", "BR"),
        ("Mexico", "MX"),
        ("Indonesia", "ID"),
        ("Vietnam", "VN"),
        ("South Africa", "ZA"),
    ])
    def test_known_countries(self, country: str, expected: str) -> None:
        assert _country_code(country) == expected

    def test_unknown_falls_back_to_slug(self) -> None:
        assert len(_country_code("Chile")) <= 3


@pytest.mark.unit
class TestParseFilename:
    def test_national_scope(self) -> None:
        r = parse_filename("Chile_NATIONAL_utility_standards.jsonl")
        assert r is not None
        country, scope, dim = r
        assert country == "Chile"
        assert scope == "national"
        assert dim == "utility_standards"

    def test_country_with_underscore(self) -> None:
        r = parse_filename("South_Africa_NATIONAL_grid_access.jsonl")
        assert r is not None
        country, scope, dim = r
        assert country == "South Africa"
        assert scope == "national"
        assert dim == "grid_access"

    def test_state_scope(self) -> None:
        r = parse_filename("Brazil_MinasGerais_cost_economics.jsonl")
        assert r is not None
        country, scope, dim = r
        assert country == "Brazil"
        assert scope == "MinasGerais"
        assert dim == "cost_economics"

    def test_unknown_dimension_returns_none(self) -> None:
        assert parse_filename("Chile_NATIONAL_unknown_dim.jsonl") is None

    def test_malformed_returns_none(self) -> None:
        assert parse_filename("randomfile.txt") is None


@pytest.mark.unit
class TestParseCollectedFile:
    def test_parses_accepted_rejected_synthesis_audit(self, tmp_path: Path) -> None:
        p = tmp_path / "Chile_NATIONAL_utility_standards.jsonl"
        lines = [
            {"status": "accepted", "fact": {
                "fact": "Chile cap is 300 kW", "source_organization": "CNE",
                "source_document": "Ley 21.118", "source_url": "https://cne.cl/x",
                "data_points": {"cap_kw": 300},
            }, "verdict": {"confidence": "high"}},
            {"status": "rejected", "fact": {}, "verdict": {"confidence": "low"}},
            {"status": "synthesis", "synthesis": {"content": "Chile DG is 300 kW.", "confidence": "high"}},
            {"status": "audit", "audit": {"corroboration_count": [2],
                                          "unsupported_sentence_indices": []}},
        ]
        p.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")

        run = parse_collected_file(p)
        assert run is not None
        assert run.country == "Chile"
        assert run.scope == "national"
        assert run.dimension == "utility_standards"
        assert len(run.accepted) == 1
        assert len(run.rejected) == 1
        assert "300 kW" in run.synthesis["content"]
        assert run.audit["corroboration_count"] == [2]

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "Chile_NATIONAL_cost_economics.jsonl"
        p.write_text("", encoding="utf-8")
        run = parse_collected_file(p)
        assert run is not None
        assert run.accepted == []

    def test_malformed_jsonl_skips_bad_lines(self, tmp_path: Path, capsys) -> None:
        p = tmp_path / "Chile_NATIONAL_grid_access.jsonl"
        p.write_text('not json\n{"status":"accepted","fact":{"fact":"x","source_url":"https://a"}}\n',
                     encoding="utf-8")
        run = parse_collected_file(p)
        assert run is not None
        assert len(run.accepted) == 1

    def test_unknown_filename_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "bogus.jsonl"
        p.write_text("", encoding="utf-8")
        assert parse_collected_file(p) is None


@pytest.mark.unit
class TestBuildDocuments:
    def test_builds_docs_from_accepted(self) -> None:
        run = CollectedRun(
            country="Chile", scope="national", dimension="utility_standards",
            accepted=[{
                "fact": {
                    "fact": "Chile cap is 300 kW",
                    "source_organization": "CNE",
                    "source_document": "Ley 21.118",
                    "source_url": "https://cne.cl/x",
                    "data_points": {"cap_kw": 300},
                },
                "verdict": {"confidence": "high"},
            }],
            rejected=[], audit={"corroboration_count": [2]},
        )
        docs = build_documents(run)
        assert len(docs) == 1
        d = docs[0]
        assert "HPC" in d["id"]
        assert d["dimension"] == "utility_standards"
        assert d["sources"][0]["url"] == "https://cne.cl/x"
        assert d["data_points"]["_hpc"]["corroborated"] is True

    def test_drops_invalid_urls(self) -> None:
        run = CollectedRun(
            country="Chile", scope="national", dimension="utility_standards",
            accepted=[{
                "fact": {"fact": "x", "source_url": "not-a-url",
                         "source_organization": "X", "source_document": "d"},
                "verdict": {},
            }],
            rejected=[], audit={},
        )
        assert build_documents(run) == []

    def test_drops_empty_content(self) -> None:
        run = CollectedRun(
            country="Chile", scope="national", dimension="utility_standards",
            accepted=[{"fact": {"fact": "", "source_url": "https://x"}, "verdict": {}}],
            rejected=[], audit={},
        )
        assert build_documents(run) == []

    def test_confidence_normalized(self) -> None:
        run = CollectedRun(
            country="Chile", scope="national", dimension="utility_standards",
            accepted=[{
                "fact": {"fact": "x", "source_url": "https://x",
                         "source_organization": "X", "source_document": "d"},
                "verdict": {"confidence": "UNKNOWN_LEVEL"},
            }],
            rejected=[], audit={},
        )
        docs = build_documents(run)
        assert docs[0]["confidence"] == "medium"


@pytest.mark.unit
class TestDedupKey:
    def test_same_content_same_key(self) -> None:
        a = {"dimension": "d1", "scope": "s1", "content": "Foo bar."}
        b = {"dimension": "d1", "scope": "s1", "content": "FOO BAR."}
        assert _dedup_key(a) == _dedup_key(b)

    def test_different_dim_different_key(self) -> None:
        a = {"dimension": "d1", "scope": "s", "content": "c"}
        b = {"dimension": "d2", "scope": "s", "content": "c"}
        assert _dedup_key(a) != _dedup_key(b)


@pytest.mark.unit
class TestMergeRunIntoCountry:
    def test_adds_national_docs(self) -> None:
        country_doc = {
            "name": "Chile", "national_documents": [], "states": [],
            "coverage_summary": {},
        }
        run = CollectedRun(
            country="Chile", scope="national", dimension="utility_standards",
            accepted=[{
                "fact": {"fact": "new fact", "source_url": "https://x",
                         "source_organization": "X", "source_document": "d"},
                "verdict": {"confidence": "high"},
            }],
            rejected=[], audit={},
        )
        out = merge_run_into_country(country_doc, run)
        assert len(out["national_documents"]) == 1
        assert country_doc["national_documents"] == []  # no mutation

    def test_deduplicates_existing_content(self) -> None:
        existing = {
            "id": "CL_NAT_UTIL_001", "dimension": "utility_standards",
            "scope": "national", "content": "existing fact",
            "sources": [{"organization": "X", "document": "d", "url": "https://x", "accessed": "2026-04-10"}],
            "confidence": "high", "last_verified": "2026-04-10", "data_points": {},
        }
        country_doc = {
            "name": "Chile", "national_documents": [existing], "states": [],
            "coverage_summary": {},
        }
        run = CollectedRun(
            country="Chile", scope="national", dimension="utility_standards",
            accepted=[{
                "fact": {"fact": "existing fact", "source_url": "https://x",
                         "source_organization": "X", "source_document": "d"},
                "verdict": {"confidence": "high"},
            }],
            rejected=[], audit={},
        )
        out = merge_run_into_country(country_doc, run)
        # should NOT double the count
        assert len(out["national_documents"]) == 1

    def test_creates_shell_state(self) -> None:
        country_doc = {
            "name": "Chile", "national_documents": [], "states": [],
            "coverage_summary": {},
        }
        run = CollectedRun(
            country="Chile", scope="Antofagasta", dimension="utility_standards",
            accepted=[{
                "fact": {"fact": "fact in state", "source_url": "https://x",
                         "source_organization": "X", "source_document": "d"},
                "verdict": {"confidence": "high"},
            }],
            rejected=[], audit={},
        )
        out = merge_run_into_country(country_doc, run)
        assert len(out["states"]) == 1
        assert out["states"][0]["name"] == "Antofagasta"


@pytest.mark.integration
class TestIngestDirectory:
    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ingest_directory(tmp_path / "nope", tmp_path, dry_run=True)

    def test_end_to_end_dry_run(self, tmp_path: Path) -> None:
        collected = tmp_path / "collected"
        kb = tmp_path / "kb"
        collected.mkdir()
        kb.mkdir()

        # seed minimal country file
        country_file = kb / "country_Chile.json"
        country_file.write_text(json.dumps({
            "name": "Chile", "national_documents": [], "states": [],
            "coverage_summary": {},
        }), encoding="utf-8")

        # collected jsonl
        jsonl = collected / "Chile_NATIONAL_utility_standards.jsonl"
        jsonl.write_text(json.dumps({
            "status": "accepted",
            "fact": {"fact": "Chile cap is 300 kW.", "source_url": "https://cne.cl/x",
                     "source_organization": "CNE", "source_document": "Ley 21.118"},
            "verdict": {"confidence": "high"},
        }) + "\n", encoding="utf-8")

        report = ingest_directory(collected, kb, dry_run=True)
        assert report.files_read == 1
        assert report.files_skipped == 0
        assert report.docs_added == 1
        assert "Chile" in report.countries_updated

        # Dry run must NOT have written
        on_disk = json.loads(country_file.read_text(encoding="utf-8"))
        assert on_disk["national_documents"] == []

    def test_skips_missing_country_file(self, tmp_path: Path, capsys) -> None:
        collected = tmp_path / "c"
        kb = tmp_path / "kb"
        collected.mkdir()
        kb.mkdir()
        jsonl = collected / "Chile_NATIONAL_utility_standards.jsonl"
        jsonl.write_text(json.dumps({
            "status": "accepted",
            "fact": {"fact": "x", "source_url": "https://x",
                     "source_organization": "X", "source_document": "d"},
            "verdict": {"confidence": "high"},
        }) + "\n", encoding="utf-8")
        report = ingest_directory(collected, kb, dry_run=True)
        assert report.docs_added == 0
