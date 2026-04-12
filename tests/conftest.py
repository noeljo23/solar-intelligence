"""Shared fixtures for PowerTrust test suite."""
from __future__ import annotations

import site
import sys

# Ensure per-user site-packages is importable even when Anaconda disables it.
# Some packages (groq, python-dotenv) land in USER_SITE when installed with
# pip install --user because Anaconda3 Lib/site-packages is not writable.
_user_site = site.getusersitepackages()
if _user_site and _user_site not in sys.path:
    sys.path.insert(0, _user_site)

import pytest

from src.schema import (
    CountryProfile,
    Document,
    Source,
    StateMetrics,
    StateProfile,
    compute_completeness,
)


@pytest.fixture
def sample_source() -> Source:
    return Source(
        organization="ANEEL",
        document="Resolucao 482/2012",
        url="https://www.aneel.gov.br/res482",
        accessed="2026-04-12",
    )


@pytest.fixture
def sample_document(sample_source: Source) -> Document:
    return Document(
        id="BR_NAT_SUBSIDIES_001",
        dimension="subsidies_incentives",
        scope="national",
        content="Brazil's net metering allows distributed generation up to 5 MW.",
        sources=(sample_source,),
        confidence="high",
        last_verified="2026-04-12",
        data_points={"max_dg_capacity_mw": 5.0},
    )


@pytest.fixture
def full_metrics() -> StateMetrics:
    return StateMetrics(
        capex_utility_usd_per_kw=900.0,
        capex_rooftop_usd_per_kw=1200.0,
        om_usd_per_kw_year=15.0,
        lcoe_usd_per_mwh=45.0,
        retail_tariff_usd_per_kwh=0.15,
        interconnection_months_avg=6.0,
        grid_congestion="low",
        curtailment_risk="low",
        ghi_kwh_m2_day=5.5,
        capacity_factor_pct=22.0,
        net_metering=True,
        accelerated_depreciation=True,
        import_duty_exempt=True,
        renewable_target_pct=30.0,
        rec_mechanism=True,
        installed_distributed_solar_mw=500.0,
    )


@pytest.fixture
def empty_metrics() -> StateMetrics:
    return StateMetrics()


@pytest.fixture
def sample_state(full_metrics: StateMetrics, sample_document: Document) -> StateProfile:
    return StateProfile(
        name="Minas Gerais",
        iso_code="BR-MG",
        metrics=full_metrics,
        documents=(sample_document,),
        data_completeness_pct=compute_completeness(full_metrics),
    )


@pytest.fixture
def sample_country(sample_state: StateProfile, sample_document: Document) -> CountryProfile:
    return CountryProfile(
        name="Brazil",
        iso_code="BR",
        currency="BRL",
        exchange_rate_to_usd=0.20,
        regulator="ANEEL",
        grid_operator="ONS",
        national_documents=(sample_document,),
        states=(sample_state,),
        last_updated="2026-04-12",
        coverage_summary={"total_docs": 2},
        data_audit={"collected": ["subsidies"], "gaps": [], "impact": []},
    )
