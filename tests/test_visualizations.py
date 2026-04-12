"""Tests for src.visualizations - chart generation smoke tests."""
from __future__ import annotations

import plotly.graph_objects as go
import pytest

from src.scoring import score_state
from src.visualizations import (
    country_comparison,
    coverage_heatmap,
    dimension_radar,
    feasibility_bar,
    kpi_card_data,
    metric_bar,
)


@pytest.fixture
def scores(sample_state):
    return [score_state(sample_state, "Brazil")]


@pytest.mark.unit
class TestFeasibilityBar:
    def test_returns_figure(self, scores) -> None:
        fig = feasibility_bar(scores)
        assert isinstance(fig, go.Figure)

    def test_empty_returns_figure(self) -> None:
        fig = feasibility_bar([])
        assert isinstance(fig, go.Figure)


@pytest.mark.unit
class TestDimensionRadar:
    def test_returns_figure(self, scores) -> None:
        fig = dimension_radar(scores[0])
        assert isinstance(fig, go.Figure)


@pytest.mark.unit
class TestMetricBar:
    def test_returns_figure(self) -> None:
        data = [
            {"state": "A", "value": 1200.0},
            {"state": "B", "value": 900.0},
        ]
        fig = metric_bar(data, metric="value", title="Test", y_label="USD/kW")
        assert isinstance(fig, go.Figure)

    def test_empty_data_returns_figure(self) -> None:
        fig = metric_bar([], metric="value", title="T", y_label="Y")
        assert isinstance(fig, go.Figure)


@pytest.mark.unit
class TestCountryComparison:
    def test_returns_figure(self) -> None:
        data = [{"country": "Brazil", "avg_score": 72.0, "states_scored": 5, "completeness": 80.0},
                {"country": "Kenya", "avg_score": 68.0, "states_scored": 2, "completeness": 55.0}]
        fig = country_comparison(data)
        assert isinstance(fig, go.Figure)

    def test_empty_returns_figure(self) -> None:
        assert isinstance(country_comparison([]), go.Figure)


@pytest.mark.unit
class TestCoverageHeatmap:
    def test_returns_figure(self) -> None:
        states = [{"name": "S1", "docs_by_dimension": {"grid_access": 3, "cost_economics": 1}}]
        fig = coverage_heatmap("TestLand", states)
        assert isinstance(fig, go.Figure)

    def test_empty_returns_figure(self) -> None:
        assert isinstance(coverage_heatmap("X", []), go.Figure)


@pytest.mark.unit
class TestKPICardData:
    def test_with_scores(self, scores) -> None:
        kpi = kpi_card_data(scores, state_count=1)
        assert kpi["states_scored"] == 1
        assert kpi["best_state"] == scores[0].state
        assert 0 <= kpi["avg_score"] <= 100

    def test_empty_scores_returns_neutral(self) -> None:
        kpi = kpi_card_data([], state_count=0)
        assert kpi["avg_score"] == 0
        assert kpi["states_scored"] == 0
        assert kpi["best_state"] == "—"
