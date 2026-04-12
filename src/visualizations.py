"""
Visualization layer: Plotly charts.

All functions take clean data structures and return Plotly Figure objects.
No business logic here — that lives in scoring.py / kb_loader.py.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from config import DIMENSION_LABELS
from src.scoring import FeasibilityScore


PALETTE = {
    "primary":   "#6366F1",  # indigo
    "secondary": "#8B5CF6",  # violet
    "bg":        "#0B0E14",
    "panel":     "#151922",
    "text":      "#E6E9EF",
    "muted":     "#8A91A5",
    "grid":      "#1F2430",
}

RATING_COLORS = {
    "Excellent":   "#22C55E",
    "Good":        "#84CC16",
    "Moderate":    "#F59E0B",
    "Challenging": "#F97316",
    "Poor":        "#EF4444",
}


def _apply_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor=PALETTE["bg"],
        font=dict(color=PALETTE["text"], family="Inter, system-ui, sans-serif", size=13),
        margin=dict(l=30, r=20, t=50, b=40),
        title=dict(font=dict(size=15, color=PALETTE["text"])),
    )
    fig.update_xaxes(gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"])
    fig.update_yaxes(gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"])
    return fig


def feasibility_bar(scores: list[FeasibilityScore]) -> go.Figure:
    if not scores:
        return _apply_theme(go.Figure().add_annotation(text="No scored states yet", showarrow=False))
    df = pd.DataFrame([{
        "State": s.state, "Score": s.total_score, "Rating": s.rating,
        "Completeness": s.data_completeness_pct,
    } for s in scores]).sort_values("Score", ascending=True)
    colors = [RATING_COLORS[r] for r in df["Rating"]]
    fig = go.Figure(go.Bar(
        x=df["Score"], y=df["State"], orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=df["Score"].map(lambda v: f"{v:.0f}"),
        textposition="outside", textfont=dict(color=PALETTE["text"]),
        customdata=df[["Rating", "Completeness"]].values,
        hovertemplate="<b>%{y}</b><br>Score %{x:.1f} · %{customdata[0]}<br>Data %{customdata[1]}%<extra></extra>",
    ))
    fig.update_layout(
        title="Feasibility by state",
        xaxis=dict(title="", range=[0, 108], showgrid=True),
        yaxis=dict(title=""),
        height=max(280, 36 * len(scores)),
        showlegend=False,
    )
    return _apply_theme(fig)


def dimension_radar(score: FeasibilityScore) -> go.Figure:
    cats = [DIMENSION_LABELS[d.dimension] for d in score.dimension_scores]
    vals = [d.score for d in score.dimension_scores]
    hover = [
        f"{DIMENSION_LABELS[d.dimension]}: {d.score:.0f}"
        + (" · imputed" if d.imputed else "")
        for d in score.dimension_scores
    ]
    fig = go.Figure(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill="toself",
        line=dict(color=PALETTE["primary"], width=2),
        fillcolor="rgba(99, 102, 241, 0.25)",
        hovertext=hover + [hover[0]], hoverinfo="text", name=score.state,
    ))
    fig.update_layout(
        title=f"{score.state} · {score.total_score:.0f}/100",
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=PALETTE["grid"],
                            tickfont=dict(size=10, color=PALETTE["muted"])),
            angularaxis=dict(gridcolor=PALETTE["grid"], tickfont=dict(size=11)),
            bgcolor=PALETTE["bg"],
        ),
        showlegend=False, height=420,
    )
    return _apply_theme(fig)


def metric_bar(data: list[dict[str, Any]], metric: str, title: str, y_label: str) -> go.Figure:
    valid = [d for d in data if d.get(metric) is not None]
    if not valid:
        fig = go.Figure().add_annotation(
            text="No data yet", showarrow=False,
            font=dict(color=PALETTE["muted"], size=13),
        )
        return _apply_theme(fig)
    df = pd.DataFrame(valid).sort_values(metric, ascending=False)
    fig = go.Figure(go.Bar(
        x=df["state"], y=df[metric],
        marker=dict(color=PALETTE["primary"], line=dict(width=0)),
        text=df[metric].map(lambda v: f"{v:,.1f}"),
        textposition="outside", textfont=dict(color=PALETTE["text"]),
    ))
    fig.update_layout(
        title=title,
        xaxis=dict(title=""),
        yaxis=dict(title=y_label),
        height=320, showlegend=False,
    )
    return _apply_theme(fig)


def country_comparison(profiles_summary: list[dict[str, Any]]) -> go.Figure:
    if not profiles_summary:
        return _apply_theme(go.Figure().add_annotation(text="No data yet", showarrow=False))
    df = pd.DataFrame(profiles_summary).sort_values("avg_score", ascending=True)
    fig = go.Figure(go.Bar(
        x=df["avg_score"], y=df["country"], orientation="h",
        marker=dict(color=PALETTE["secondary"], line=dict(width=0)),
        text=df["avg_score"].map(lambda v: f"{v:.0f}"),
        textposition="outside", textfont=dict(color=PALETTE["text"]),
        customdata=df[["states_scored", "completeness"]].values,
        hovertemplate="<b>%{y}</b><br>Avg %{x:.1f}<br>%{customdata[0]} states · %{customdata[1]}%<extra></extra>",
    ))
    fig.update_layout(
        title="Across countries",
        xaxis=dict(title="", range=[0, 108]),
        yaxis=dict(title=""),
        height=max(260, 36 * len(profiles_summary)),
        showlegend=False,
    )
    return _apply_theme(fig)


def coverage_heatmap(country_name: str, states: list[dict[str, Any]]) -> go.Figure:
    if not states:
        return _apply_theme(go.Figure().add_annotation(text="No states", showarrow=False))
    dim_keys = list(DIMENSION_LABELS.keys())
    z, y_labels = [], []
    for s in states:
        y_labels.append(s["name"])
        z.append([s["docs_by_dimension"].get(dk, 0) for dk in dim_keys])
    fig = go.Figure(go.Heatmap(
        z=z,
        x=[DIMENSION_LABELS[k] for k in dim_keys], y=y_labels,
        colorscale=[
            [0.0, "#151922"],
            [0.15, "#1E2539"],
            [0.4, "#3B3A8F"],
            [0.7, "#6366F1"],
            [1.0, "#A5B4FC"],
        ],
        hovertemplate="%{y} · %{x}<br>%{z} docs<extra></extra>",
        colorbar=dict(tickfont=dict(color=PALETTE["muted"], size=10)),
    ))
    fig.update_layout(
        title=f"{country_name}: documents by dimension",
        height=max(260, 28 * len(states)),
    )
    return _apply_theme(fig)


def kpi_card_data(scores: list[FeasibilityScore], state_count: int) -> dict[str, Any]:
    if not scores:
        return {"avg_score": 0, "best_state": "—", "best_score": 0,
                "states_scored": 0, "avg_completeness": 0}
    best = max(scores, key=lambda s: s.total_score)
    return {
        "avg_score": round(sum(s.total_score for s in scores) / len(scores), 1),
        "best_state": best.state,
        "best_score": best.total_score,
        "states_scored": len(scores),
        "avg_completeness": round(sum(s.data_completeness_pct for s in scores) / len(scores), 1),
    }


# Backwards-compat alias for existing tests referencing POWERTRUST_PALETTE
POWERTRUST_PALETTE = PALETTE
