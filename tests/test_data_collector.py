"""Tests for src.data_collector - pure helpers + mock-backed agents."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.data_collector import (
    CandidateFact,
    CollectorAgent,
    ScoutAgent,
    SynthesizerAgent,
    ValidatorAgent,
    _chunk_text,
    _looks_like_empty_placeholder,
    html_to_text,
)


def _mock_groq(responses: list[dict]) -> MagicMock:
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
class TestHtmlToText:
    def test_strips_tags(self) -> None:
        assert html_to_text("<p>hi <b>there</b></p>") == "hi there"

    def test_removes_scripts(self) -> None:
        html = "<div>keep</div><script>evil()</script><style>x</style>"
        assert "evil" not in html_to_text(html)
        assert "keep" in html_to_text(html)

    def test_decodes_entities(self) -> None:
        assert "& <" in html_to_text("&amp; &lt;")

    def test_empty_input(self) -> None:
        assert html_to_text("") == ""


@pytest.mark.unit
class TestPlaceholderDetection:
    @pytest.mark.parametrize("fact,source,expected", [
        ("", "some source", True),
        ("fact", "", True),
        ("no relevant information found", "has source", True),
        ("NO FACTS were extracted", "has source", True),
        ("Chile cap is 300 kW", "source text here", False),
    ])
    def test_placeholder_detection(self, fact: str, source: str, expected: bool) -> None:
        assert _looks_like_empty_placeholder(fact, source) is expected


@pytest.mark.unit
class TestChunkText:
    def test_no_chunking_if_short(self) -> None:
        text = "a" * 100
        assert _chunk_text(text, chunk_chars=200) == [text]

    def test_chunks_with_overlap(self) -> None:
        text = "a" * 500
        chunks = _chunk_text(text, chunk_chars=200, overlap=50)
        assert len(chunks) >= 2
        assert all(len(c) <= 200 for c in chunks)

    def test_empty_text(self) -> None:
        assert _chunk_text("", chunk_chars=100) == [""]


@pytest.mark.unit
class TestCollectorAgent:
    def test_no_groq_returns_empty(self) -> None:
        agent = CollectorAgent(groq_client=None)
        out = agent.propose_facts(
            country="Chile", state=None, dimension="utility_standards",
            source_url="https://x", source_organization="X",
            source_document="doc", source_text="some text",
        )
        assert out == []

    def test_empty_source_text_returns_empty(self) -> None:
        agent = CollectorAgent(groq_client=MagicMock())
        out = agent.propose_facts(
            country="Chile", state=None, dimension="utility_standards",
            source_url="https://x", source_organization="X",
            source_document="doc", source_text="",
        )
        assert out == []

    def test_parses_facts_from_mock_groq(self) -> None:
        agent = CollectorAgent(groq_client=_mock_groq([{
            "facts": [
                {"fact": "Chile cap is 300 kW.",
                 "source_text": "The cap is 300 kW per connection point.",
                 "data_points": {"cap_kw": 300}},
                {"fact": "Net billing, not net metering.",
                 "source_text": "Surplus credited at injection price.",
                 "data_points": {}},
            ]
        }]))
        out = agent.propose_facts(
            country="Chile", state=None, dimension="utility_standards",
            source_url="https://cne.cl/x", source_organization="CNE",
            source_document="Ley 21.118", source_text="Ley 21.118 raised the cap.",
        )
        assert len(out) == 2
        assert out[0].fact == "Chile cap is 300 kW."
        assert out[0].data_points == {"cap_kw": 300}

    def test_filters_placeholder_facts(self) -> None:
        agent = CollectorAgent(groq_client=_mock_groq([{
            "facts": [
                {"fact": "no relevant information", "source_text": "irrelevant"},
                {"fact": "Real fact here.", "source_text": "real source."},
            ]
        }]))
        out = agent.propose_facts(
            country="Chile", state=None, dimension="utility_standards",
            source_url="https://x", source_organization="X",
            source_document="doc", source_text="src",
        )
        assert len(out) == 1
        assert out[0].fact == "Real fact here."

    def test_deduplicates_by_content(self) -> None:
        agent = CollectorAgent(groq_client=_mock_groq([{
            "facts": [
                {"fact": "Same fact here.", "source_text": "src 1"},
                {"fact": "same fact here.", "source_text": "src 2"},
            ]
        }]))
        out = agent.propose_facts(
            country="X", state=None, dimension="cost_economics",
            source_url="https://x", source_organization="X",
            source_document="d", source_text="t",
        )
        assert len(out) == 1


@pytest.mark.unit
class TestValidatorAgent:
    def test_no_groq_rejects(self, monkeypatch) -> None:
        monkeypatch.setattr("src.data_collector.GROQ_API_KEY", "")
        cand = CandidateFact(
            fact="x", source_text="src", source_url="https://x",
            source_organization="X", source_document="d",
            country="C", state=None, dimension="cost_economics", data_points={},
        )
        v = ValidatorAgent(groq_client=None).validate(cand)
        assert v.accepted is False
        assert "GROQ_API_KEY" in v.reason

    def test_empty_source_rejects(self) -> None:
        cand = CandidateFact(
            fact="x", source_text="", source_url="https://x",
            source_organization="X", source_document="d",
            country="C", state=None, dimension="cost_economics", data_points={},
        )
        v = ValidatorAgent(groq_client=MagicMock()).validate(cand)
        assert v.accepted is False

    def test_accepts_when_llm_says_yes(self) -> None:
        cand = CandidateFact(
            fact="cap is 300 kW",
            source_text="The cap is 300 kW per connection.",
            source_url="https://x", source_organization="X",
            source_document="d", country="C", state=None,
            dimension="utility_standards", data_points={},
        )
        agent = ValidatorAgent(groq_client=_mock_groq([
            {"accepted": True, "reason": "source literal", "confidence": "high"}
        ]))
        v = agent.validate(cand)
        assert v.accepted is True
        assert v.confidence == "high"

    def test_rejects_on_parse_error(self) -> None:
        client = MagicMock()
        msg = MagicMock()
        msg.content = "not json"
        choice = MagicMock()
        choice.message = msg
        out = MagicMock()
        out.choices = [choice]
        client.chat.completions.create.return_value = out
        cand = CandidateFact(
            fact="x", source_text="s", source_url="https://x",
            source_organization="X", source_document="d",
            country="C", state=None, dimension="cost_economics", data_points={},
        )
        v = ValidatorAgent(groq_client=client).validate(cand)
        assert v.accepted is False


@pytest.mark.unit
class TestScoutAgent:
    def test_no_groq_returns_empty(self, monkeypatch) -> None:
        monkeypatch.setattr("src.data_collector.GROQ_API_KEY", "")
        assert ScoutAgent(groq_client=None).propose_urls("Chile", None, "cost_economics") == []

    def test_filters_non_http_urls(self) -> None:
        agent = ScoutAgent(groq_client=_mock_groq([{
            "urls": [
                {"url": "https://cne.cl", "organization": "CNE", "document": "x", "rationale": "y"},
                {"url": "javascript:alert(1)", "organization": "X", "document": "x", "rationale": "y"},
                {"url": "ftp://x", "organization": "Y", "document": "x", "rationale": "y"},
            ]
        }]))
        out = agent.propose_urls("Chile", None, "cost_economics")
        assert len(out) == 1
        assert out[0]["url"] == "https://cne.cl"


@pytest.mark.unit
class TestSynthesizerAgent:
    def test_no_groq_returns_low_confidence(self) -> None:
        result = SynthesizerAgent(groq_client=None).synthesize(
            country="C", state=None, dimension="cost_economics", accepted_facts=[]
        )
        assert result["content"] == ""
        assert result["confidence"] == "low"

    def test_no_facts_returns_empty(self) -> None:
        result = SynthesizerAgent(groq_client=MagicMock()).synthesize(
            country="C", state=None, dimension="cost_economics", accepted_facts=[]
        )
        assert result["content"] == ""

    def test_synthesizes_prose_from_facts(self) -> None:
        facts = [CandidateFact(
            fact="Chile cap is 300 kW",
            source_text="src", source_url="https://x",
            source_organization="CNE", source_document="Ley 21.118",
            country="Chile", state=None, dimension="utility_standards",
            data_points={"cap_kw": 300},
        )]
        agent = SynthesizerAgent(groq_client=_mock_groq([{
            "content": "Chile's DG cap is 300 kW.",
            "data_points": {"cap_kw": 300},
            "confidence": "high",
        }]))
        r = agent.synthesize("Chile", None, "utility_standards", facts)
        assert "300 kW" in r["content"]
        assert r["confidence"] == "high"
