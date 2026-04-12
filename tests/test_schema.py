"""Tests for src.schema - validation, serialization, and completeness."""
from __future__ import annotations

import pytest

from src.schema import (
    Document,
    Source,
    StateMetrics,
    compute_completeness,
    document_to_dict,
    validate_country,
)


@pytest.mark.unit
class TestSource:
    def test_valid_source_passes_validation(self, sample_source: Source) -> None:
        sample_source.validate()

    def test_missing_organization_fails(self) -> None:
        s = Source(organization="", document="Res 1", url="https://x.gov", accessed="2026-04-12")
        with pytest.raises(ValueError, match="organization"):
            s.validate()

    def test_missing_document_fails(self) -> None:
        s = Source(organization="ANEEL", document="", url="https://x.gov", accessed="2026-04-12")
        with pytest.raises(ValueError, match="organization and document"):
            s.validate()

    def test_bad_url_scheme_fails(self) -> None:
        s = Source(organization="A", document="D", url="ftp://x.gov", accessed="2026-04-12")
        with pytest.raises(ValueError, match="invalid url"):
            s.validate()

    def test_bad_date_format_fails(self) -> None:
        s = Source(organization="A", document="D", url="https://x.gov", accessed="04/12/2026")
        with pytest.raises(ValueError, match="accessed must be ISO date"):
            s.validate()

    def test_frozen_dataclass_rejects_mutation(self, sample_source: Source) -> None:
        with pytest.raises(Exception):
            sample_source.organization = "OTHER"  # type: ignore[misc]


@pytest.mark.unit
class TestDocument:
    def test_valid_document_passes(self, sample_document: Document) -> None:
        sample_document.validate()

    def test_invalid_confidence_fails(self, sample_source: Source) -> None:
        d = Document(
            id="X", dimension="subsidies_incentives", scope="national",
            content="x", sources=(sample_source,),
            confidence="super-high", last_verified="2026-04-12",
        )
        with pytest.raises(ValueError, match="confidence"):
            d.validate()

    def test_no_sources_fails(self) -> None:
        d = Document(
            id="X", dimension="grid_access", scope="national",
            content="x", sources=(), confidence="high", last_verified="2026-04-12",
        )
        with pytest.raises(ValueError, match="no sources"):
            d.validate()

    def test_invalid_nested_source_fails(self) -> None:
        bad_source = Source(organization="", document="", url="", accessed="")
        d = Document(
            id="X", dimension="grid_access", scope="national",
            content="x", sources=(bad_source,),
            confidence="high", last_verified="2026-04-12",
        )
        with pytest.raises(ValueError):
            d.validate()


@pytest.mark.unit
class TestCompleteness:
    def test_all_filled_is_100(self, full_metrics: StateMetrics) -> None:
        assert compute_completeness(full_metrics) == 100.0

    def test_empty_is_zero(self, empty_metrics: StateMetrics) -> None:
        assert compute_completeness(empty_metrics) == 0.0

    def test_half_filled(self) -> None:
        m = StateMetrics(capex_utility_usd_per_kw=900.0, ghi_kwh_m2_day=5.0)
        pct = compute_completeness(m)
        assert 0.0 < pct < 50.0


@pytest.mark.unit
class TestSerialization:
    def test_document_roundtrip_preserves_fields(self, sample_document: Document) -> None:
        d = document_to_dict(sample_document)
        assert d["id"] == sample_document.id
        assert d["dimension"] == sample_document.dimension
        assert len(d["sources"]) == 1
        assert d["sources"][0]["organization"] == "ANEEL"
        assert d["data_points"] == {"max_dg_capacity_mw": 5.0}


@pytest.mark.unit
class TestCountryValidation:
    def test_valid_country_has_no_errors(self, sample_country) -> None:
        assert validate_country(sample_country) == []

    def test_missing_iso_reports_error(self, sample_country) -> None:
        from dataclasses import replace
        bad = replace(sample_country, iso_code="")
        errors = validate_country(bad)
        assert any("iso_code" in e for e in errors)
