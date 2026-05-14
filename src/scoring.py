"""
Feasibility scoring engine.

Produces a 0-100 feasibility score per state based on weighted
normalized scores across the six dimensions. Every score is
explainable — we record the sub-scores that make up the total.

Design: scores are computed only from real verified metrics.
If a metric is missing, that dimension contributes its weight *
a baseline 50 (neutral) with an explicit flag that data was imputed.
The UI surfaces this imputation so nothing is hidden.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import SCORING_WEIGHTS
from src.schema import StateMetrics, StateProfile


# -- Normalization bounds (global, developing-market oriented) --
# These are calibrated across developing solar markets. A state that
# hits the 'best' bound scores 100; 'worst' bound scores 0; linear between.
BOUNDS: dict[str, tuple[float, float, str]] = {
    # (worst, best, direction) — direction 'lower_better' or 'higher_better'
    "capex_utility_usd_per_kw": (1500.0, 600.0, "lower_better"),
    "capex_rooftop_usd_per_kw": (2000.0, 800.0, "lower_better"),
    "interconnection_months_avg": (24.0, 3.0, "lower_better"),
    "retail_tariff_usd_per_kwh": (0.05, 0.25, "higher_better"),
    "ghi_kwh_m2_day": (3.5, 6.5, "higher_better"),
    "renewable_target_pct": (0.0, 40.0, "higher_better"),
}

CATEGORICAL_SCORES: dict[str, dict[str, float]] = {
    "grid_congestion": {"low": 90, "moderate": 55, "high": 25},
    "curtailment_risk": {"low": 90, "moderate": 55, "high": 25},
}


@dataclass(frozen=True)
class DimensionScore:
    """Score for a single dimension with explanation."""
    dimension: str
    score: float               # 0..100
    inputs_used: tuple[str, ...]
    inputs_missing: tuple[str, ...]
    imputed: bool              # True if any input was missing


@dataclass(frozen=True)
class FeasibilityScore:
    """Composite feasibility result."""
    state: str
    country: str
    total_score: float
    rating: str                # "Excellent" | "Good" | "Moderate" | "Challenging" | "Poor"
    dimension_scores: tuple[DimensionScore, ...]
    data_completeness_pct: float


def _normalize_numeric(value: float, metric_key: str) -> float | None:
    """Normalize a numeric value to 0..100 using BOUNDS."""
    if metric_key not in BOUNDS:
        return None
    worst, best, direction = BOUNDS[metric_key]
    if direction == "lower_better":
        if value <= best:
            return 100.0
        if value >= worst:
            return 0.0
        return round(100.0 * (worst - value) / (worst - best), 1)
    # higher_better
    if value >= best:
        return 100.0
    if value <= worst:
        return 0.0
    return round(100.0 * (value - worst) / (best - worst), 1)


def _categorical_score(value: str | None, key: str) -> float | None:
    if value is None or key not in CATEGORICAL_SCORES:
        return None
    return CATEGORICAL_SCORES[key].get(value.lower())


def _score_cost_economics(m: StateMetrics) -> DimensionScore:
    inputs_used: list[str] = []
    inputs_missing: list[str] = []
    components: list[float] = []

    for key in ("capex_utility_usd_per_kw", "capex_rooftop_usd_per_kw", "retail_tariff_usd_per_kwh"):
        val = getattr(m, key)
        if val is None:
            inputs_missing.append(key)
            continue
        s = _normalize_numeric(val, key)
        if s is not None:
            components.append(s)
            inputs_used.append(key)

    if not components:
        return DimensionScore("cost_economics", 50.0, (), tuple(inputs_missing), imputed=True)

    return DimensionScore(
        dimension="cost_economics",
        score=round(sum(components) / len(components), 1),
        inputs_used=tuple(inputs_used),
        inputs_missing=tuple(inputs_missing),
        imputed=bool(inputs_missing),
    )


def _score_grid_access(m: StateMetrics) -> DimensionScore:
    inputs_used: list[str] = []
    inputs_missing: list[str] = []
    components: list[float] = []

    if m.interconnection_months_avg is not None:
        components.append(_normalize_numeric(m.interconnection_months_avg, "interconnection_months_avg") or 50)
        inputs_used.append("interconnection_months_avg")
    else:
        inputs_missing.append("interconnection_months_avg")

    congestion_score = _categorical_score(m.grid_congestion, "grid_congestion")
    if congestion_score is not None:
        components.append(congestion_score)
        inputs_used.append("grid_congestion")
    else:
        inputs_missing.append("grid_congestion")

    curtail_score = _categorical_score(m.curtailment_risk, "curtailment_risk")
    if curtail_score is not None:
        components.append(curtail_score)
        inputs_used.append("curtailment_risk")
    else:
        inputs_missing.append("curtailment_risk")

    if not components:
        return DimensionScore("grid_access", 50.0, (), tuple(inputs_missing), imputed=True)

    return DimensionScore(
        dimension="grid_access",
        score=round(sum(components) / len(components), 1),
        inputs_used=tuple(inputs_used),
        inputs_missing=tuple(inputs_missing),
        imputed=bool(inputs_missing),
    )


def _score_subsidies(m: StateMetrics) -> DimensionScore:
    """Binary policy flags → additive scoring."""
    flags = {
        "net_metering": m.net_metering,
        "accelerated_depreciation": m.accelerated_depreciation,
        "import_duty_exempt": m.import_duty_exempt,
    }
    inputs_used = tuple(k for k, v in flags.items() if v is not None)
    inputs_missing = tuple(k for k, v in flags.items() if v is None)
    if not inputs_used:
        return DimensionScore("subsidies_incentives", 50.0, (), inputs_missing, imputed=True)

    # Each positive flag gives 33 points (3 flags = 99). +1 for rec_mechanism bonus.
    count_yes = sum(1 for k in inputs_used if flags[k] is True)
    score = round(33.3 * count_yes + (1 if m.rec_mechanism else 0), 1)
    score = min(score, 100.0)
    return DimensionScore(
        dimension="subsidies_incentives",
        score=score,
        inputs_used=inputs_used,
        inputs_missing=inputs_missing,
        imputed=bool(inputs_missing),
    )


def _score_utility_standards(m: StateMetrics) -> DimensionScore:
    inputs_used: list[str] = []
    inputs_missing: list[str] = []
    components: list[float] = []

    if m.renewable_target_pct is not None:
        s = _normalize_numeric(m.renewable_target_pct, "renewable_target_pct") or 0
        components.append(s)
        inputs_used.append("renewable_target_pct")
    else:
        inputs_missing.append("renewable_target_pct")

    if m.rec_mechanism is not None:
        components.append(80.0 if m.rec_mechanism else 30.0)
        inputs_used.append("rec_mechanism")
    else:
        inputs_missing.append("rec_mechanism")

    if not components:
        return DimensionScore("utility_standards", 50.0, (), tuple(inputs_missing), imputed=True)

    return DimensionScore(
        dimension="utility_standards",
        score=round(sum(components) / len(components), 1),
        inputs_used=tuple(inputs_used),
        inputs_missing=tuple(inputs_missing),
        imputed=bool(inputs_missing),
    )


def _score_public_comment(state: StateProfile) -> DimensionScore:
    """Qualitative: presence of public comment documents indicates transparency.

    Scoring heuristic: having documented public comment processes is good
    signal for a functioning regulatory environment.
    """
    docs = [d for d in state.documents if d.dimension == "public_comment"]
    if not docs:
        return DimensionScore("public_comment", 50.0, (), ("public_comment_data",), imputed=True)

    # If we have documents, score reflects number of documented cases (capped)
    score = min(100.0, 60.0 + 10.0 * len(docs))
    return DimensionScore(
        dimension="public_comment",
        score=round(score, 1),
        inputs_used=("public_comment_documents",),
        inputs_missing=(),
        imputed=False,
    )


def _score_unknown_unknowns(state: StateProfile) -> DimensionScore:
    """Heuristic: # of documented risks (higher = better-understood risk profile).

    Paradox: more documented unknown-unknowns == HIGHER score, because it means
    we understand the market's risks. A state with zero documented risks is
    not risk-free — it's under-researched. Score penalizes lack of research.
    """
    docs = [d for d in state.documents if d.dimension == "unknown_unknowns"]
    if not docs:
        return DimensionScore("unknown_unknowns", 40.0, (), ("risk_research",), imputed=True)

    score = min(100.0, 50.0 + 10.0 * len(docs))
    return DimensionScore(
        dimension="unknown_unknowns",
        score=round(score, 1),
        inputs_used=("documented_risks",),
        inputs_missing=(),
        imputed=False,
    )


def rating_from_score(total: float) -> str:
    if total >= 80:
        return "Excellent"
    if total >= 65:
        return "Good"
    if total >= 50:
        return "Moderate"
    if total >= 35:
        return "Challenging"
    return "Poor"


def score_state(state: StateProfile, country: str) -> FeasibilityScore:
    """Compute feasibility score for a single state."""
    dim_scores = (
        _score_cost_economics(state.metrics),
        _score_grid_access(state.metrics),
        _score_subsidies(state.metrics),
        _score_utility_standards(state.metrics),
        _score_public_comment(state),
        _score_unknown_unknowns(state),
    )

    total = sum(ds.score * SCORING_WEIGHTS[ds.dimension] for ds in dim_scores)
    return FeasibilityScore(
        state=state.name,
        country=country,
        total_score=round(total, 1),
        rating=rating_from_score(total),
        dimension_scores=dim_scores,
        data_completeness_pct=state.data_completeness_pct,
    )


def score_country(country_name: str, states: tuple[StateProfile, ...]) -> list[FeasibilityScore]:
    """Score every state in a country."""
    return [score_state(s, country_name) for s in states]
