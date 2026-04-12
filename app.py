"""
PowerTrust Solar Intelligence — Streamlit entry point.

Multi-country distributed solar research platform. Every answer is
grounded in verified, source-cited data. The app is organized as a
sidebar-navigated single-page application with five sections:

  1. Dashboard — KPIs, cross-country comparison, feasibility ranking
  2. Country Deep-Dive — per-state metrics, radar, dimension breakdowns
  3. Chat — grounded multi-turn RAG over verified KB
  4. Data Audit — coverage, gaps, and their decision impact
  5. Methodology — how the system is updated and extended
"""
from __future__ import annotations

import streamlit as st

from config import GROQ_API_KEY, KB_DIR, SUPPORTED_COUNTRIES
from src.kb_loader import load_all_countries
from src.rag_engine import RAGEngine
from src.scoring import score_country
from src.views import (
    render_chat,
    render_country_deep_dive,
    render_dashboard,
    render_data_audit,
    render_methodology,
)


st.set_page_config(
    page_title="PowerTrust Solar Intelligence",
    page_icon="[SUN]",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner="Loading verified knowledge base...")
def load_kb():
    return load_all_countries(KB_DIR)


@st.cache_resource(show_spinner="Preparing retrieval index for {country}...")
def get_rag_engine(country: str):
    profiles = load_kb()
    profile = profiles.get(country)
    engine = RAGEngine(country=country)
    if profile is not None:
        # Index if not already — check empty collection
        count = engine._backend.count()  # noqa: SLF001 — intentional
        if count == 0:
            engine.index_country(profile)
    return engine


def sidebar() -> tuple[str, str]:
    """Render sidebar. Returns (view, country)."""
    st.sidebar.markdown("## PowerTrust")
    st.sidebar.markdown("### Solar Intelligence")
    st.sidebar.caption("Open-Data Research for Distributed Solar Development")

    profiles = load_kb()
    available = sorted(profiles.keys())
    # Show all configured countries but mark unavailable as 'coming soon'
    country_options = []
    for c in SUPPORTED_COUNTRIES:
        if c in available:
            country_options.append(c)
        else:
            country_options.append(f"{c} (coming soon)")

    selection = st.sidebar.selectbox(
        "Country",
        country_options,
        index=0 if country_options else None,
        help="Switch markets. Countries marked 'coming soon' have data collection scheduled.",
    )
    country = selection.replace(" (coming soon)", "") if selection else ""

    st.sidebar.divider()
    view = st.sidebar.radio(
        "View",
        ["Dashboard", "Country Deep-Dive", "Chat", "Data Audit", "Methodology"],
        label_visibility="visible",
    )

    st.sidebar.divider()
    st.sidebar.caption("System status")
    if GROQ_API_KEY:
        st.sidebar.success("LLM: Groq connected")
    else:
        st.sidebar.error("LLM: GROQ_API_KEY missing (.env)")
    st.sidebar.caption(f"Countries loaded: {len(available)} / {len(SUPPORTED_COUNTRIES)}")

    return view, country


def main() -> None:
    profiles = load_kb()
    view, country = sidebar()

    # Header
    col1, col2 = st.columns([5, 2])
    with col1:
        st.title("PowerTrust Solar Intelligence")
        st.caption("Grounded, source-cited research for distributed solar development in emerging markets.")

    if country not in profiles:
        st.warning(f"**{country}** is in the coverage roadmap but has no verified data yet.")
        st.info(
            "The HPC data collection pipeline (see hpc/submit_collection.slurm) can populate this country "
            "on demand. Until then, this country is hidden from chat / dashboards to prevent misleading output."
        )
        render_methodology()
        return

    profile = profiles[country]
    scores = score_country(profile.name, profile.states)

    if view == "Dashboard":
        render_dashboard(profile, scores, profiles)
    elif view == "Country Deep-Dive":
        render_country_deep_dive(profile, scores)
    elif view == "Chat":
        engine = get_rag_engine(country)
        render_chat(profile, engine)
    elif view == "Data Audit":
        render_data_audit(profile)
    elif view == "Methodology":
        render_methodology()


if __name__ == "__main__":
    main()
