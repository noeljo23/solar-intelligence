"""Tests for src.views - helpers after native-widget rewrite."""
from __future__ import annotations

import pytest

from src.schema import Document, Source
from src.views import (
    CONFIDENCE_ICON,
    RATING_ICON,
    _country_rating,
    _is_hpc_doc,
    _next_action_short,
)


@pytest.mark.unit
class TestCountryRating:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (85.0, "Excellent"),
            (70.0, "Good"),
            (55.0, "Moderate"),
            (40.0, "Challenging"),
            (10.0, "Poor"),
            (80.0, "Excellent"),   # boundary
            (65.0, "Good"),        # boundary
            (50.0, "Moderate"),    # boundary
            (35.0, "Challenging"), # boundary
        ],
    )
    def test_ratings(self, score: float, expected: str) -> None:
        assert _country_rating(score) == expected


@pytest.mark.unit
class TestIsHPCDoc:
    def test_hpc_id_marker(self) -> None:
        d = Document(
            id="Chile_NATIONAL_HPC_0",
            dimension="utility_standards",
            scope="national",
            content="x",
            sources=(Source("IEA", "report", "https://iea.org", "2026-04-12"),),
            confidence="medium",
            last_verified="2026-04-12",
        )
        assert _is_hpc_doc(d) is True

    def test_non_hpc_doc(self) -> None:
        d = Document(
            id="Chile_manual_entry_01",
            dimension="utility_standards",
            scope="national",
            content="x",
            sources=(Source("CNE", "doc", "https://cne.cl", "2026-04-12"),),
            confidence="high",
            last_verified="2026-04-12",
        )
        assert _is_hpc_doc(d) is False


@pytest.mark.unit
class TestNextActionShort:
    def test_strong_country_suggests_pilot(self, sample_country) -> None:
        from src.scoring import FeasibilityScore
        fake = FeasibilityScore(
            state="TopState", country="X", total_score=75.0,
            rating="Good", dimension_scores=(), data_completeness_pct=80.0,
        )
        msg = _next_action_short(sample_country, fake, 75.0)
        assert "TopState" in msg
        assert "pilot" in msg.lower()

    def test_middling_country_is_opportunistic(self, sample_country) -> None:
        from src.scoring import FeasibilityScore
        fake = FeasibilityScore(
            state="TopState", country="X", total_score=55.0,
            rating="Moderate", dimension_scores=(), data_completeness_pct=60.0,
        )
        msg = _next_action_short(sample_country, fake, 55.0)
        assert "opportunistic" in msg.lower()

    def test_weak_country_is_hold(self, sample_country) -> None:
        from src.scoring import FeasibilityScore
        fake = FeasibilityScore(
            state="TopState", country="X", total_score=30.0,
            rating="Poor", dimension_scores=(), data_completeness_pct=40.0,
        )
        msg = _next_action_short(sample_country, fake, 30.0)
        assert "hold" in msg.lower()


@pytest.mark.unit
class TestIconMaps:
    def test_rating_icons_cover_all_tiers(self) -> None:
        for tier in ("Excellent", "Good", "Moderate", "Challenging", "Poor"):
            assert tier in RATING_ICON

    def test_confidence_icons_cover_tiers(self) -> None:
        for tier in ("high", "medium", "low"):
            assert tier in CONFIDENCE_ICON
