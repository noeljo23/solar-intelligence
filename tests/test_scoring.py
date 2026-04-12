"""Tests for src.scoring - feasibility scoring engine."""
from __future__ import annotations

import pytest

from src.schema import StateMetrics, StateProfile
from src.scoring import (
    FeasibilityScore,
    _normalize_numeric,
    _rating,
    score_country,
    score_state,
)


@pytest.mark.unit
class TestNormalize:
    @pytest.mark.parametrize("val,key,expected", [
        (600.0, "capex_utility_usd_per_kw", 100.0),
        (1500.0, "capex_utility_usd_per_kw", 0.0),
        (1050.0, "capex_utility_usd_per_kw", 50.0),
        (3.0, "interconnection_months_avg", 100.0),
        (24.0, "interconnection_months_avg", 0.0),
        (6.5, "ghi_kwh_m2_day", 100.0),
        (3.5, "ghi_kwh_m2_day", 0.0),
        (5.0, "ghi_kwh_m2_day", 50.0),
    ])
    def test_normalize_at_bounds(self, val: float, key: str, expected: float) -> None:
        assert _normalize_numeric(val, key) == pytest.approx(expected, abs=0.5)

    def test_below_lower_bound_clamps_to_zero(self) -> None:
        assert _normalize_numeric(2000.0, "capex_utility_usd_per_kw") == 0.0

    def test_above_upper_bound_clamps_to_100(self) -> None:
        assert _normalize_numeric(100.0, "capex_utility_usd_per_kw") == 100.0

    def test_unknown_metric_returns_none(self) -> None:
        assert _normalize_numeric(500.0, "nonexistent_metric") is None


@pytest.mark.unit
class TestRating:
    @pytest.mark.parametrize("score,expected", [
        (95.0, "Excellent"),
        (80.0, "Excellent"),
        (70.0, "Good"),
        (65.0, "Good"),
        (55.0, "Moderate"),
        (50.0, "Moderate"),
        (40.0, "Challenging"),
        (35.0, "Challenging"),
        (20.0, "Poor"),
        (0.0, "Poor"),
    ])
    def test_rating_thresholds(self, score: float, expected: str) -> None:
        assert _rating(score) == expected


@pytest.mark.unit
class TestScoreState:
    def test_full_metrics_produces_high_score(self, sample_state: StateProfile) -> None:
        result = score_state(sample_state, "Brazil")
        assert isinstance(result, FeasibilityScore)
        assert result.state == "Minas Gerais"
        assert result.country == "Brazil"
        assert result.total_score > 60
        assert result.rating in ("Good", "Excellent")

    def test_empty_metrics_produces_neutral_score(self, empty_metrics: StateMetrics) -> None:
        state = StateProfile(
            name="Empty", iso_code=None, metrics=empty_metrics,
            documents=(), data_completeness_pct=0.0,
        )
        result = score_state(state, "TestCountry")
        assert 30.0 <= result.total_score <= 60.0
        assert all(ds.imputed for ds in result.dimension_scores
                   if ds.dimension in ("cost_economics", "grid_access",
                                        "subsidies_incentives", "utility_standards"))

    def test_dimension_scores_sum_count(self, sample_state: StateProfile) -> None:
        result = score_state(sample_state, "Brazil")
        assert len(result.dimension_scores) == 6
        dims = {ds.dimension for ds in result.dimension_scores}
        assert dims == {"cost_economics", "grid_access", "subsidies_incentives",
                        "utility_standards", "public_comment", "unknown_unknowns"}

    def test_score_is_bounded_0_to_100(self, sample_state: StateProfile) -> None:
        result = score_state(sample_state, "Brazil")
        assert 0.0 <= result.total_score <= 100.0
        for ds in result.dimension_scores:
            assert 0.0 <= ds.score <= 100.0


@pytest.mark.unit
class TestScoreCountry:
    def test_score_country_returns_list(self, sample_country) -> None:
        results = score_country(sample_country.name, sample_country.states)
        assert len(results) == len(sample_country.states)
        for r in results:
            assert r.country == "Brazil"

    def test_score_country_with_empty_states_returns_empty(self) -> None:
        assert score_country("X", ()) == []
