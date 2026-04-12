"""Tests for src.language - translation-risk detection."""
from __future__ import annotations

import pytest

from src.language import (
    badge,
    caveat_for_languages,
    detect_language,
    detect_languages_from_sources_str,
    language_name,
    needs_caveat,
)


@pytest.mark.unit
class TestDetectLanguage:
    @pytest.mark.parametrize("url,organization,expected", [
        ("https://www.planalto.gov.br/ccivil_03/_ato2015-2018/lei123.htm", "Planalto", "pt"),
        ("https://www.aneel.gov.br/res482", "ANEEL", "pt"),
        ("https://www.gob.mx/cre", "CRE", "es"),
        ("https://www.bcn.cl/leychile/123", "BCN", "es"),
        ("https://www.cne.cl/en/", "CNE", "es"),
        ("https://www.creg.gov.co/res030", "CREG", "es"),
        ("https://jdih.esdm.go.id", "ESDM", "id"),
        ("https://moit.gov.vn/policy", "MOIT", "vi"),
        ("https://www.st.gov.my/nem3", "SEDA", "en"),
        ("https://nerc.gov.ng/act", "NERC", "en"),
        ("https://www.epra.go.ke/", "EPRA", "en"),
        ("https://www.nersa.org.za", "NERSA", "en"),
    ])
    def test_url_detection(self, url: str, organization: str, expected: str) -> None:
        assert detect_language(url, organization) == expected

    def test_empty_url_defaults_to_english(self) -> None:
        assert detect_language("", "") == "en"

    def test_unknown_url_defaults_to_english(self) -> None:
        assert detect_language("https://example.com/article", "Acme") == "en"

    def test_org_hint_backup_when_url_unknown(self) -> None:
        assert detect_language("https://unknown.com", "ANEEL") == "pt"
        assert detect_language("https://unknown.com", "CENACE") == "es"


@pytest.mark.unit
class TestLanguageName:
    @pytest.mark.parametrize("code,expected", [
        ("en", "English"),
        ("pt", "Portuguese"),
        ("es", "Spanish"),
        ("id", "Bahasa Indonesia"),
        ("vi", "Vietnamese"),
    ])
    def test_known_codes(self, code: str, expected: str) -> None:
        assert language_name(code) == expected

    def test_unknown_code_returns_uppercase(self) -> None:
        assert language_name("zz") == "ZZ"

    def test_empty_returns_unknown(self) -> None:
        assert language_name("") == "Unknown"


@pytest.mark.unit
class TestNeedsCaveat:
    @pytest.mark.parametrize("code,expected", [
        ("en", False),
        ("EN", False),
        ("pt", True),
        ("es", True),
        ("", False),
    ])
    def test_caveat(self, code: str, expected: bool) -> None:
        assert needs_caveat(code) is expected


@pytest.mark.unit
class TestBadge:
    def test_english_badge(self) -> None:
        assert badge("en") == "EN"

    def test_non_english_badge_upper(self) -> None:
        assert badge("pt") == "PT"
        assert badge("es") == "ES"


@pytest.mark.unit
class TestParseSourcesString:
    def test_empty_string_returns_empty_list(self) -> None:
        assert detect_languages_from_sources_str("") == []

    def test_single_source(self) -> None:
        s = "ANEEL: Res 482 (2026-04-12) <https://www.aneel.gov.br/r>"
        assert detect_languages_from_sources_str(s) == ["pt"]

    def test_multiple_sources_dedup(self) -> None:
        s = ("ANEEL: r1 (2026-04-12) <https://aneel.gov.br/a> | "
             "CREG: r2 (2026-04-12) <https://creg.gov.co/b>")
        langs = detect_languages_from_sources_str(s)
        assert set(langs) == {"pt", "es"}

    def test_mixed_english_and_non_english(self) -> None:
        s = ("NERC: Act (2026-04-12) <https://nerc.gov.ng/a> | "
             "CNE: Reg (2026-04-12) <https://www.cne.cl/b>")
        langs = detect_languages_from_sources_str(s)
        assert "en" in langs and "es" in langs


@pytest.mark.unit
class TestCaveatForLanguages:
    def test_only_english_returns_empty(self) -> None:
        assert caveat_for_languages(["en"]) == ""

    def test_empty_returns_empty(self) -> None:
        assert caveat_for_languages([]) == ""

    def test_non_english_returns_caveat(self) -> None:
        c = caveat_for_languages(["pt", "es"])
        assert "Portuguese" in c
        assert "Spanish" in c
        assert "verify" in c.lower()

    def test_mixed_filters_english(self) -> None:
        c = caveat_for_languages(["en", "pt"])
        assert "Portuguese" in c
        assert "English" not in c
