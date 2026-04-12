"""Tests for src.kb_loader - country JSON loading and validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.kb_loader import iter_all_documents, load_all_countries, load_country


KB_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"


@pytest.mark.integration
class TestLoadCountry:
    def test_brazil_loads_cleanly(self) -> None:
        profile = load_country(KB_DIR / "country_Brazil.json")
        assert profile.name == "Brazil"
        assert profile.iso_code == "BR"
        assert profile.regulator.startswith("ANEEL")
        assert len(profile.national_documents) > 0
        assert len(profile.states) > 0

    def test_all_kb_files_valid(self) -> None:
        paths = sorted(KB_DIR.glob("country_*.json"))
        assert len(paths) >= 10, "expected 10+ country KBs"
        for p in paths:
            profile = load_country(p)
            assert profile.name
            assert profile.iso_code
            assert profile.regulator
            assert profile.grid_operator

    def test_document_fields_are_valid(self) -> None:
        for p in sorted(KB_DIR.glob("country_*.json")):
            profile = load_country(p)
            for doc in iter_all_documents(profile):
                assert doc.id
                assert doc.confidence in ("high", "medium", "low")
                assert len(doc.sources) >= 1
                for src in doc.sources:
                    assert src.url.startswith(("http://", "https://"))


@pytest.mark.integration
class TestLoadAllCountries:
    def test_loads_at_least_10_countries(self) -> None:
        profiles = load_all_countries(KB_DIR)
        assert len(profiles) >= 10
        assert "Brazil" in profiles
        assert "Chile" in profiles
        assert "Malaysia" in profiles
        assert "Kenya" in profiles

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_all_countries(tmp_path / "nonexistent") == {}

    def test_bad_file_is_skipped(self, tmp_path: Path, capsys) -> None:
        # Valid dir, invalid content
        bad = tmp_path / "country_Bogus.json"
        bad.write_text('{"name": "Bogus"}', encoding="utf-8")
        profiles = load_all_countries(tmp_path)
        assert "Bogus" not in profiles
        captured = capsys.readouterr()
        assert "SKIPPED" in captured.out

    def test_non_json_file_is_skipped(self, tmp_path: Path) -> None:
        bad = tmp_path / "country_Broken.json"
        bad.write_text("not json at all {{", encoding="utf-8")
        profiles = load_all_countries(tmp_path)
        assert "Broken" not in profiles


@pytest.mark.integration
class TestIterAllDocuments:
    def test_flattens_national_and_state_docs(self) -> None:
        profile = load_country(KB_DIR / "country_Brazil.json")
        docs = iter_all_documents(profile)
        nat_count = len(profile.national_documents)
        state_count = sum(len(s.documents) for s in profile.states)
        assert len(docs) == nat_count + state_count
