"""
Streamlit view renderers.

Native widgets only. No inline HTML.
Short labels, progressive disclosure via tabs.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config import DIMENSION_LABELS, DIMENSIONS
from src.language import detect_language, language_name, needs_caveat
from src.schema import CountryProfile, Document
from src.scoring import FeasibilityScore, rating_from_score, score_country
from src.visualizations import (
    country_comparison,
    coverage_heatmap,
    dimension_radar,
    feasibility_bar,
    kpi_card_data,
    metric_bar,
)


RATING_ICON = {
    "Excellent":   "🟢",
    "Good":        "🟢",
    "Moderate":    "🟡",
    "Challenging": "🟠",
    "Poor":        "🔴",
}

CONFIDENCE_ICON = {"high": "✓", "medium": "○", "low": "·"}


def _is_hpc_doc(doc: Document) -> bool:
    return "_HPC_" in doc.id or "hpc" in doc.id.lower()


# ---------------- Dashboard ----------------

def render_dashboard(
    profile: CountryProfile,
    scores: list[FeasibilityScore],
    all_profiles: dict[str, CountryProfile],
) -> None:
    st.subheader(profile.name)
    st.caption(
        f"{profile.regulator} · {profile.grid_operator} · "
        f"{profile.currency} {profile.exchange_rate_to_usd}/USD · updated {profile.last_updated}"
    )

    if not scores:
        st.info(f"No scored states for {profile.name} yet.")
        return

    # Headline
    avg = round(sum(s.total_score for s in scores) / len(scores), 1)
    rating = rating_from_score(avg)
    best = max(scores, key=lambda s: s.total_score)
    total_docs = len(profile.national_documents) + sum(len(s.documents) for s in profile.states)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Score", f"{avg:.0f}", f"{RATING_ICON[rating]} {rating}")
    k2.metric("Top state", best.state, f"{best.total_score:.0f}/100")
    k3.metric("States", len(scores))
    k4.metric("Documents", total_docs)

    st.write("")

    tab_rank, tab_metrics, tab_compare = st.tabs(["Ranking", "Metrics", "Compare"])

    with tab_rank:
        left, right = st.columns([3, 2])
        with left:
            st.plotly_chart(feasibility_bar(scores), use_container_width=True)
        with right:
            with st.container(border=True):
                st.caption("RECOMMENDATION")
                st.markdown(_next_action_short(profile, best, avg))

    with tab_metrics:
        rows = _state_metric_rows(profile)
        m1, m2 = st.columns(2)
        with m1:
            st.plotly_chart(
                metric_bar(rows, "capex_utility_usd_per_kw",
                           "CAPEX utility (USD/kW)", ""),
                use_container_width=True,
            )
            st.plotly_chart(
                metric_bar(rows, "retail_tariff_usd_per_kwh",
                           "Retail tariff (USD/kWh)", ""),
                use_container_width=True,
            )
        with m2:
            st.plotly_chart(
                metric_bar(rows, "interconnection_months_avg",
                           "Interconnection wait (months)", ""),
                use_container_width=True,
            )
            st.plotly_chart(
                metric_bar(rows, "ghi_kwh_m2_day",
                           "Solar irradiance (kWh/m²/day)", ""),
                use_container_width=True,
            )

    with tab_compare:
        summaries = _country_summaries(all_profiles)
        st.plotly_chart(country_comparison(summaries), use_container_width=True)


def _next_action_short(profile: CountryProfile, best: FeasibilityScore, avg: float) -> str:
    if avg >= 65:
        return f"**Shortlist {best.state}** for a pilot. Verify interconnection timing before capex."
    gaps = profile.data_audit.get("gaps", [])
    if avg >= 50:
        return f"**Opportunistic.** Close {len(gaps)} data gaps first, then re-evaluate {best.state}."
    return "**Hold.** Wait for updated regulator data or HPC re-run."


def _country_summaries(profiles: dict[str, CountryProfile]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, p in profiles.items():
        s = score_country(name, p.states)
        if not s:
            continue
        out.append({
            "country": name,
            "avg_score": round(sum(x.total_score for x in s) / len(s), 1),
            "states_scored": len(s),
            "completeness": round(sum(x.data_completeness_pct for x in s) / len(s), 1),
        })
    return out


def _state_metric_rows(profile: CountryProfile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in profile.states:
        row = {"state": s.name}
        for k, v in s.metrics.__dict__.items():
            row[k] = v
        rows.append(row)
    return rows


# ---------------- Deep Dive ----------------

def render_country_deep_dive(profile: CountryProfile, scores: list[FeasibilityScore]) -> None:
    st.subheader(f"{profile.name} · deep dive")

    if not profile.states:
        st.warning("No state-level data loaded.")
        return

    state_names = [s.name for s in profile.states]
    selected = st.selectbox("State", state_names, label_visibility="collapsed")
    state = next(s for s in profile.states if s.name == selected)
    score = next((sc for sc in scores if sc.state == selected), None)

    if score:
        k1, k2, k3 = st.columns(3)
        k1.metric("Feasibility", f"{score.total_score:.0f}",
                  f"{RATING_ICON[score.rating]} {score.rating}")
        k2.metric("Data coverage", f"{state.data_completeness_pct}%")
        k3.metric("Documents", len(state.documents))

    st.write("")

    tab_scores, tab_metrics, tab_sources = st.tabs(["Scores", "Metrics", "Sources"])

    with tab_scores:
        if score:
            left, right = st.columns([3, 2])
            with left:
                st.plotly_chart(dimension_radar(score), use_container_width=True)
            with right:
                df = pd.DataFrame([
                    {
                        "Dimension": DIMENSION_LABELS[d.dimension],
                        "Score": round(d.score, 0),
                        "Status": "imputed" if d.imputed else "verified",
                    }
                    for d in score.dimension_scores
                ])
                st.dataframe(df, hide_index=True, use_container_width=True)

    with tab_metrics:
        rows = [
            {"Metric": k.replace("_", " "), "Value": v if v is not None else "—"}
            for k, v in state.metrics.__dict__.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with tab_sources:
        st.caption("Grouped by dimension. Expand to see citations.")
        for dim in DIMENSIONS:
            docs = [d for d in state.documents if d.dimension == dim]
            with st.expander(f"{DIMENSION_LABELS[dim]} · {len(docs)}"):
                if not docs:
                    st.caption("No documents yet.")
                    continue
                for d in docs:
                    _render_document(d)


def _render_document(d: Document) -> None:
    with st.container(border=True):
        langs = sorted({detect_language(s.url, s.organization) for s in d.sources})
        caveat = any(needs_caveat(c) for c in langs)
        tags = []
        tags.append(f"{CONFIDENCE_ICON.get(d.confidence, '·')} {d.confidence}")
        if _is_hpc_doc(d):
            tags.append("HPC")
        if caveat:
            non_en = [language_name(c) for c in langs if needs_caveat(c)]
            tags.append(f"⚠ {', '.join(non_en)}")
        st.caption(" · ".join(tags) + f" · verified {d.last_verified}")
        st.write(d.content)
        for src in d.sources:
            st.caption(f"{src.organization} — [{src.document}]({src.url}) · {src.accessed}")


# ---------------- Chat ----------------

_SUGGESTED_QUERIES: tuple[str, ...] = (
    "Average CAPEX for 1 MW rooftop solar?",
    "Which state has the fastest grid interconnection?",
    "Best mix of irradiance + short wait times?",
    "What data is missing that would shift our CAPEX estimate?",
    "Key regulatory risks in this country?",
)


def render_chat(profile: CountryProfile, engine) -> None:
    st.subheader(f"Ask about {profile.name}")
    st.caption("Answers cite verified sources. Missing data is surfaced, not guessed.")

    if "chat_country" not in st.session_state or st.session_state.chat_country != profile.name:
        st.session_state.chat_country = profile.name
        st.session_state.history = []
        st.session_state.pending_prompt = ""

    if not st.session_state.history:
        cols = st.columns(len(_SUGGESTED_QUERIES))
        for i, q in enumerate(_SUGGESTED_QUERIES):
            if cols[i].button(q, key=f"suggest_{i}", use_container_width=True):
                st.session_state.pending_prompt = q

    if st.session_state.history:
        if st.button("Clear"):
            st.session_state.history = []
            st.session_state.pending_prompt = ""
            st.rerun()

    for turn in st.session_state.history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
            if turn.get("sources"):
                with st.expander(f"Sources · {len(turn['sources'])}"):
                    _render_source_list(turn["sources"])

    prompt = st.chat_input("Ask about cost, grid, policy, risk…")
    if not prompt and st.session_state.get("pending_prompt"):
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = ""

    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving…"):
                history_for_llm = [
                    {"role": t["role"], "content": t["content"]}
                    for t in st.session_state.history[:-1]
                ]
                response = engine.chat(prompt, history=history_for_llm)
            st.markdown(response.answer)
            if response.sources_used:
                with st.expander(f"Sources · {len(response.sources_used)}"):
                    _render_source_list(response.sources_used)
        st.session_state.history.append({
            "role": "assistant",
            "content": response.answer,
            "sources": list(response.sources_used),
        })


def _render_source_list(sources: list[dict[str, Any]]) -> None:
    for s in sources:
        tags = [CONFIDENCE_ICON.get(s.get("confidence", ""), "·") + " " + s.get("confidence", "")]
        if "_HPC_" in str(s.get("id", "")):
            tags.append("HPC")
        with st.container(border=True):
            st.caption(
                f"**[{s['id']}]** · {' · '.join(tags)} · {s['scope']} · "
                f"{s['dimension']} · verified {s['verified']}"
            )
            if s.get("sources"):
                st.caption(s["sources"])


# ---------------- Data Audit ----------------

def render_data_audit(profile: CountryProfile) -> None:
    st.subheader(f"{profile.name} · data audit")
    st.caption("What is sourced, what is missing, what it means for decisions.")

    hpc_count = sum(1 for s in profile.states for d in s.documents if _is_hpc_doc(d)) + \
        sum(1 for d in profile.national_documents if _is_hpc_doc(d))
    total_docs = sum(len(s.documents) for s in profile.states) + len(profile.national_documents)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("States", len(profile.states))
    k2.metric("Documents", total_docs)
    k3.metric("National", len(profile.national_documents))
    k4.metric("HPC-collected", hpc_count)

    st.write("")

    tab_cov, tab_gaps, tab_hpc = st.tabs(["Coverage", "Gaps", "HPC quality"])

    with tab_cov:
        state_rows = [
            {"name": s.name,
             "docs_by_dimension": _docs_by_dim(s.documents)}
            for s in profile.states
        ]
        st.plotly_chart(coverage_heatmap(profile.name, state_rows), use_container_width=True)

    with tab_gaps:
        audit = profile.data_audit
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**✓ Collected**")
            for item in audit.get("collected", []) or ["—"]:
                st.markdown(f"- {item}")
        with c2:
            st.markdown("**⚠ Missing**")
            for item in audit.get("gaps", []) or ["—"]:
                st.markdown(f"- {item}")
        with c3:
            st.markdown("**→ Impact**")
            for item in audit.get("impact", []) or ["—"]:
                st.markdown(f"- {item}")

    with tab_hpc:
        hpc_audit = profile.coverage_summary.get("hpc_audit") if isinstance(
            profile.coverage_summary, dict
        ) else None
        if not hpc_audit:
            st.info("No HPC audit data for this country yet.")
            return
        h1, h2, h3 = st.columns(3)
        corr = hpc_audit.get("corroboration_rate_pct")
        cite = hpc_audit.get("citation_rate_pct")
        rej = hpc_audit.get("facts_rejected")
        if corr is not None:
            h1.metric("Corroboration", f"{corr}%",
                      help="Facts confirmed by ≥2 independent sources")
        if cite is not None:
            h2.metric("Citation rate", f"{cite}%",
                      help="Facts with verbatim source quote")
        if rej is not None:
            h3.metric("Rejected", rej,
                      help="Rejected by validator agent")


def _docs_by_dim(documents) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in documents:
        out[d.dimension] = out.get(d.dimension, 0) + 1
    return out


# ---------------- Methodology ----------------

def render_methodology() -> None:
    st.subheader("How this works")

    tab_pipeline, tab_hpc, tab_extend = st.tabs(["Pipeline", "HPC", "Extend"])

    with tab_pipeline:
        st.markdown("""
**Two-agent validation.** No fact enters the KB without passing both.

1. **Collector** — extracts candidate facts with verbatim source quotes.
2. **Validator** — re-reads the source adversarially. Rejects on any mismatch or inference.
3. **Persist** — accepted facts carry organization, document, URL, access date, confidence.

Every retrieved chunk carries provenance into the LLM context. Chat always cites sources.
Missing data is flagged, not guessed. Feasibility scores mark imputed dimensions.
""")

    with tab_hpc:
        st.markdown("""
Heavy collection runs on Northeastern's Explorer H200 cluster.

```bash
sbatch hpc/submit_collection.slurm hpc/batches/<country>_batch.jsonl
```

- Partition: `gpu --constraint=h200`, 8 h max
- Llama 3.3 70B on a single H200 via vLLM (141 GB HBM3e)
- Batch parallelism: 4 workers per job
""")

    with tab_extend:
        st.markdown("""
To add a country:

1. Write `hpc/batches/<country>_batch.jsonl` — one line per (state, dimension, sources)
2. `sbatch hpc/submit_collection.slurm ...`
3. Run local validation pass
4. Merge to `data/knowledge_base/country_<name>.json`
5. Country appears in the sidebar on next reload
""")
