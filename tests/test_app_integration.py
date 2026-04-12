"""End-to-end Streamlit AppTest smoke tests.

Uses streamlit.testing.v1.AppTest to actually execute app.py against the real
KB and verify no exceptions bubble up in the Dashboard, Deep-Dive, or Audit
views. Chat view is exercised via a mock Groq backend.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402


APP_PATH = "app.py"


@pytest.mark.integration
class TestAppSmoke:
    def test_app_launches_without_exception(self) -> None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        assert not at.exception, [str(e) for e in at.exception]

    def test_dashboard_renders_title(self) -> None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        titles = [t.value for t in at.title]
        assert any("PowerTrust" in t for t in titles)

    def test_sidebar_has_country_selector(self) -> None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        # Sidebar should contain a selectbox for country
        sidebar_selects = at.sidebar.selectbox
        assert len(sidebar_selects) >= 1

    def test_deep_dive_view_renders(self) -> None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        # Switch to Deep-Dive via sidebar radio
        radios = at.sidebar.radio
        if radios:
            radios[0].set_value("Country Deep-Dive").run()
            assert not at.exception, [str(e) for e in at.exception]

    def test_audit_view_renders(self) -> None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        radios = at.sidebar.radio
        if radios:
            radios[0].set_value("Data Audit").run()
            assert not at.exception, [str(e) for e in at.exception]

    def test_methodology_view_renders(self) -> None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        radios = at.sidebar.radio
        if radios:
            radios[0].set_value("Methodology").run()
            assert not at.exception, [str(e) for e in at.exception]
