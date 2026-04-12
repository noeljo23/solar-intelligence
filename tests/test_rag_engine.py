"""Tests for src.rag_engine - in-memory retrieval backend + embedding."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.rag_engine import (
    RAGEngine,
    RetrievalResult,
    _InMemoryBackend,
    _cosine,
    _hash_embed,
    _matches_filter,
)


@pytest.mark.unit
class TestHashEmbed:
    def test_dimension_matches(self) -> None:
        v = _hash_embed("solar energy policy")
        assert len(v) == 384

    def test_empty_text_returns_zero_vector(self) -> None:
        v = _hash_embed("")
        assert len(v) == 384
        assert all(x == 0.0 for x in v)

    def test_deterministic(self) -> None:
        a = _hash_embed("grid interconnection in Malaysia")
        b = _hash_embed("grid interconnection in Malaysia")
        assert a == b

    def test_similar_text_has_higher_cosine(self) -> None:
        a = _hash_embed("solar net metering policy")
        b = _hash_embed("solar net metering incentives")
        c = _hash_embed("unrelated banana cryptography topic")
        assert _cosine(a, b) > _cosine(a, c)

    def test_custom_dim_respected(self) -> None:
        v = _hash_embed("test", dim=128)
        assert len(v) == 128


@pytest.mark.unit
class TestCosine:
    def test_identical_vectors_return_one(self) -> None:
        v = [1.0, 0.0, 0.0]
        assert _cosine(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self) -> None:
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_zero_vector_returns_zero(self) -> None:
        assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


@pytest.mark.unit
class TestMatchesFilter:
    def test_equality_match(self) -> None:
        assert _matches_filter({"scope": "national"}, {"scope": "national"}) is True

    def test_equality_mismatch(self) -> None:
        assert _matches_filter({"scope": "state"}, {"scope": "national"}) is False

    def test_and_all_match(self) -> None:
        where = {"$and": [{"scope": "national"}, {"dimension": "grid_access"}]}
        meta = {"scope": "national", "dimension": "grid_access"}
        assert _matches_filter(meta, where) is True

    def test_and_one_mismatch(self) -> None:
        where = {"$and": [{"scope": "national"}, {"dimension": "grid_access"}]}
        meta = {"scope": "national", "dimension": "subsidies_incentives"}
        assert _matches_filter(meta, where) is False


@pytest.mark.unit
class TestInMemoryBackend:
    def test_add_and_count(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        b = _InMemoryBackend("testcol")
        assert b.count() == 0
        b.add(
            ids=["d1", "d2"],
            contents=["first doc", "second doc"],
            metadatas=[{"dimension": "grid_access"}, {"dimension": "subsidies_incentives"}],
            embeddings=[_hash_embed("first doc"), _hash_embed("second doc")],
        )
        assert b.count() == 2

    def test_query_filters_by_dimension(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        b = _InMemoryBackend("testcol_filter")
        b.add(
            ids=["d1", "d2"],
            contents=["grid doc", "subsidy doc"],
            metadatas=[{"dimension": "grid_access"}, {"dimension": "subsidies_incentives"}],
            embeddings=[_hash_embed("grid interconnection"), _hash_embed("tax subsidy")],
        )
        hits = b.query(_hash_embed("grid interconnection"), k=5, where={"dimension": "grid_access"})
        assert len(hits) == 1
        assert hits[0][0] == "d1"

    def test_query_empty_backend_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        b = _InMemoryBackend("testcol_empty")
        assert b.query(_hash_embed("anything"), k=5, where=None) == []

    def test_reset_clears_storage(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        b = _InMemoryBackend("testcol_reset")
        b.add(ids=["d1"], contents=["x"], metadatas=[{}], embeddings=[_hash_embed("x")])
        assert b.count() == 1
        b.reset()
        assert b.count() == 0

    def test_persistence_across_instances(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        b1 = _InMemoryBackend("testcol_persist")
        b1.add(ids=["d1"], contents=["persisted"], metadatas=[{"x": 1}], embeddings=[_hash_embed("p")])
        b2 = _InMemoryBackend("testcol_persist")
        assert b2.count() == 1

    def test_query_returns_top_k(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        b = _InMemoryBackend("testcol_topk")
        n = 10
        b.add(
            ids=[f"d{i}" for i in range(n)],
            contents=[f"doc {i}" for i in range(n)],
            metadatas=[{"i": i} for i in range(n)],
            embeddings=[_hash_embed(f"doc {i}") for i in range(n)],
        )
        hits = b.query(_hash_embed("doc 3"), k=3, where=None)
        assert len(hits) == 3


@pytest.mark.integration
class TestRAGEngine:
    def test_index_and_retrieve_country(self, sample_country, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        engine = RAGEngine(country="Brazil", collection_suffix="test")
        n = engine.index_country(sample_country)
        assert n == 2  # 1 national + 1 state doc

        results = engine.retrieve("net metering distributed generation", k=5)
        assert len(results) >= 1
        assert isinstance(results[0], RetrievalResult)

    def test_retrieve_with_dimension_filter(self, sample_country, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        engine = RAGEngine(country="Brazil", collection_suffix="test_filter")
        engine.index_country(sample_country)
        results = engine.retrieve("policy", k=5, dimension="subsidies_incentives")
        assert all(r.metadata.get("dimension") == "subsidies_incentives" for r in results)

    def test_retrieve_empty_kb_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        engine = RAGEngine(country="EmptyLand", collection_suffix="test_empty")
        assert engine.retrieve("anything") == []

    def test_chat_without_groq_returns_informative_message(
        self, sample_country, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("src.rag_engine.CHROMA_DIR", tmp_path)
        engine = RAGEngine(country="Brazil", collection_suffix="test_chat")
        engine.index_country(sample_country)
        # force no groq client
        engine._groq = None
        resp = engine.chat("What's the CAPEX?")
        assert "GROQ_API_KEY" in resp.answer
        assert resp.sources_used == ()
