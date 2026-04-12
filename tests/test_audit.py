"""Tests for src.audit - mock-backed Groq client to exercise the audit agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.audit import (
    AuditorAgent,
    FactClaim,
    _empty_report,
    run_audit,
    split_sentences,
)


def _mock_groq(responses: list[dict]) -> MagicMock:
    """Build a mock Groq client that returns json-encoded responses in order."""
    client = MagicMock()
    iterator = iter(responses)

    def _create(**_kwargs):
        try:
            payload = next(iterator)
        except StopIteration:
            payload = {}
        msg = MagicMock()
        msg.content = json.dumps(payload)
        choice = MagicMock()
        choice.message = msg
        out = MagicMock()
        out.choices = [choice]
        return out

    client.chat.completions.create.side_effect = _create
    return client


@pytest.mark.unit
class TestSplitSentences:
    def test_basic(self) -> None:
        assert split_sentences("One sentence. Two? Three!") == [
            "One sentence.", "Two?", "Three!",
        ]

    def test_empty(self) -> None:
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_no_terminators(self) -> None:
        assert split_sentences("no terminators here") == ["no terminators here"]


@pytest.mark.unit
class TestEmptyReport:
    def test_returns_issue(self) -> None:
        r = _empty_report(["a.", "b."], n_alternates=2)
        assert "auditor unavailable" in r.issues
        assert r.citations == [[], []]
        assert r.consistency_support == [0, 0]

    def test_empty_sentences(self) -> None:
        r = _empty_report([], n_alternates=0)
        assert r.sentences == []
        assert r.citations == []


@pytest.mark.unit
class TestCorroborate:
    def test_empty_facts(self) -> None:
        agent = AuditorAgent(groq_client=MagicMock())
        clusters, counts = agent.corroborate([])
        assert clusters == []
        assert counts == []

    def test_no_groq_returns_singletons(self, monkeypatch) -> None:
        monkeypatch.setattr("src.audit.GROQ_API_KEY", "")
        facts = [
            FactClaim(1, "fact A", "https://a.com"),
            FactClaim(2, "fact B", "https://b.com"),
        ]
        agent = AuditorAgent(groq_client=None)
        clusters, counts = agent.corroborate(facts)
        assert clusters == [[1], [2]]
        assert counts == [1, 1]

    def test_cluster_counts_distinct_urls(self) -> None:
        facts = [
            FactClaim(1, "cap = 300 kW", "https://bcn.cl/a"),
            FactClaim(2, "cap = 300 kW", "https://cne.cl/b"),
            FactClaim(3, "cap = 100 kW", "https://gov.cl/c"),
        ]
        agent = AuditorAgent(
            groq_client=_mock_groq([{"clusters": [[1, 2], [3]]}])
        )
        clusters, counts = agent.corroborate(facts)
        assert clusters == [[1, 2], [3]]
        assert counts == [2, 2, 1]

    def test_malformed_json_falls_back(self) -> None:
        facts = [FactClaim(1, "a", "https://x"), FactClaim(2, "b", "https://y")]
        client = MagicMock()
        msg = MagicMock()
        msg.content = "not json"
        choice = MagicMock()
        choice.message = msg
        out = MagicMock()
        out.choices = [choice]
        client.chat.completions.create.return_value = out
        agent = AuditorAgent(groq_client=client)
        clusters, counts = agent.corroborate(facts)
        assert clusters == [[1], [2]]
        assert counts == [1, 1]


@pytest.mark.unit
class TestAuditCitations:
    def test_empty_sentences(self) -> None:
        agent = AuditorAgent(groq_client=MagicMock())
        c, u = agent.audit_citations([], [FactClaim(1, "x", "https://y")])
        assert c == []
        assert u == []

    def test_empty_facts_all_unsupported(self) -> None:
        agent = AuditorAgent(groq_client=MagicMock())
        c, u = agent.audit_citations(["s1.", "s2."], [])
        assert c == [[], []]
        assert u == [0, 1]

    def test_citations_returned(self) -> None:
        sents = ["Chile cap is 300 kW.", "Net-billing applies."]
        facts = [FactClaim(1, "300 kW cap", "https://a"),
                 FactClaim(2, "net-billing scheme", "https://b")]
        agent = AuditorAgent(groq_client=_mock_groq([
            {"citations": [[1], [2]]}
        ]))
        c, u = agent.audit_citations(sents, facts)
        assert c == [[1], [2]]
        assert u == []

    def test_unsupported_detected(self) -> None:
        sents = ["Supported sentence.", "Unsupported sentence."]
        facts = [FactClaim(1, "fact", "https://a")]
        agent = AuditorAgent(groq_client=_mock_groq([
            {"citations": [[1], []]}
        ]))
        c, u = agent.audit_citations(sents, facts)
        assert u == [1]


@pytest.mark.unit
class TestConsistencyCheck:
    def test_no_alternates(self) -> None:
        agent = AuditorAgent(groq_client=MagicMock())
        assert agent.consistency_check(["s1.", "s2."], []) == [0, 0]

    def test_no_primary(self) -> None:
        agent = AuditorAgent(groq_client=MagicMock())
        assert agent.consistency_check([], ["alt draft."]) == []

    def test_counts_echoes(self) -> None:
        agent = AuditorAgent(groq_client=_mock_groq([
            {"supports": [[True, True], [True, False]]}
        ]))
        res = agent.consistency_check(["s1.", "s2."], ["alt1", "alt2"])
        assert res == [2, 1]


@pytest.mark.unit
class TestRunAuditIntegration:
    def test_no_groq_returns_empty_report(self, monkeypatch) -> None:
        monkeypatch.setattr("src.audit.GROQ_API_KEY", "")
        auditor = AuditorAgent(groq_client=None)
        r = run_audit(
            primary_content="Only sentence.",
            alternate_contents=["alt."],
            accepted_facts=[("fact 1", "https://x")],
            auditor=auditor,
        )
        assert "auditor unavailable" in r.issues
        assert r.sentences == ["Only sentence."]

    def test_full_path_with_mock(self) -> None:
        auditor = AuditorAgent(groq_client=_mock_groq([
            {"clusters": [[1]]},                    # corroborate
            {"citations": [[1]]},                   # audit_citations
            {"supports": [[True]]},                 # consistency_check
        ]))
        r = run_audit(
            primary_content="Chile has a 300 kW cap.",
            alternate_contents=["Chile's distributed generation is capped at 300 kW."],
            accepted_facts=[("Chile 300 kW", "https://x")],
            auditor=auditor,
        )
        assert r.sentences == ["Chile has a 300 kW cap."]
        assert r.corroboration_count == [1]
        assert r.citations == [[1]]
        assert r.consistency_support == [1]
