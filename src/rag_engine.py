"""
RAG engine: embedding, retrieval, and grounded generation.

Design principles:
- Zero hallucination: LLM responses are strictly grounded in retrieved context.
- Explicit 'data not available': when context insufficient, say so.
- Citations always: every answer carries source references.
- Multi-turn: conversation history maintained per session.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hashlib
import json
import math
import os
import re

from groq import Groq

from config import (
    CHROMA_DIR,
    GROQ_API_KEY,
    MODEL_SYNTHESIS,
    RETRIEVAL_TOP_K,
)
from src.schema import CountryProfile, Document, document_to_dict
from src.kb_loader import iter_all_documents
from src.language import (
    caveat_for_languages,
    detect_language,
    detect_languages_from_sources_str,
    language_name,
)

# ChromaDB is optional. On some platforms (Windows + chromadb 1.5.x + missing
# MSVC runtime) it segfaults during `add()`. When that happens we use the
# in-memory backend instead. Set SOLAR_RAG_BACKEND=memory to force.
_FORCE_MEMORY = os.environ.get("SOLAR_RAG_BACKEND", "").lower() == "memory"
try:
    if _FORCE_MEMORY:
        raise ImportError("forced memory backend")
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
    _CHROMA_OK = True
except ImportError:
    _CHROMA_OK = False


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,}")


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic, dependency-free sentence embedding (blake2b bag-of-words).

    Chroma's default MiniLM-ONNX embedder requires a working onnxruntime DLL,
    which fails on some Windows installs. Pre-computing a pure-Python hash
    embedding and passing it to Chroma via the `embeddings=` argument lets
    retrieval work on ANY platform. Quality is lower than MiniLM but adequate
    for a small regulatory corpus where exact-keyword matching dominates.
    """
    vec = [0.0] * dim
    tokens = _WORD_RE.findall((text or "").lower())
    if not tokens:
        return vec
    for token in tokens:
        h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if (h[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


SYSTEM_PROMPT = """You are Solis — a grounded research assistant for distributed solar market analysis.

HARD RULE — NEVER LEAK THE RETRIEVAL SYSTEM.
Never mention "context", "provided context", "the documents", "the knowledge base", "the sources don't", "not mentioned", "no information is given", or any similar phrase. These words expose implementation details and are forbidden in every response.

If you know the fact: state it and cite it.
If you do NOT know the fact: reply with ONE sentence, exactly: "No verified data on [the specific fact]." Nothing more. No filler, no suggestion, no apology.

ABSOLUTE RULES:
1. Answer ONLY from the FACTS supplied in this turn.
   - Broad questions ("rules for X", "overview of Y"): summarize what the FACTS cover. Group by topic (net metering, tariffs, incentives, grid access, etc.). Do not refuse just because the question is broad.
   - Specific questions where the fact is absent: use the exact one-line refusal above.
2. Do not pivot. If the question asks for fact X and only adjacent fact Y is available, refuse on X — do not answer with Y.
3. NEVER invent numbers, dates, policies, URLs, or facts. If a number is missing, omit it.
4. Cite sources inline using [Source: Organization, Document, Date]. Cite only sources that directly support the sentence they follow.
5. State scope explicitly: national vs state-specific.
6. If data is older than 12 months, flag it once — do not repeat.
7. Write for an energy-sector analyst: technical, confident, decision-oriented. No hedging, no fluff.
8. TRANSLATION DISCLOSURE: ONLY when your answer actually quotes or paraphrases translated content, append once at the end: "⚠ Translated from [language] — verify numbers against the original." One line total. Never append this line on a refusal.

RESPONSE STRUCTURE:
- Direct answer first (2–4 sentences), with inline citations.
- Supporting bullets only if they add specifics not in the opening paragraph.
- Stop when the question is answered.
"""


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieved document with similarity score."""
    document_id: str
    content: str
    metadata: dict[str, Any]
    distance: float


@dataclass(frozen=True)
class ChatResponse:
    """LLM response with grounding trace."""
    answer: str
    sources_used: tuple[dict[str, Any], ...]
    retrieved_ids: tuple[str, ...]


class _InMemoryBackend:
    """Dependency-free backend: json-on-disk + in-memory cosine search.

    Used when ChromaDB is unavailable or unstable (e.g. Windows segfaults in
    chromadb 1.5.x HNSW). For a 120-doc corpus, brute-force cosine over
    pre-computed 384-dim vectors runs in under a millisecond — no HNSW
    needed.
    """

    def __init__(self, collection_name: str) -> None:
        self._path = CHROMA_DIR / f"{collection_name}.json"
        self._ids: list[str] = []
        self._contents: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._embeddings: list[list[float]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._ids = list(data.get("ids", []))
            self._contents = list(data.get("contents", []))
            self._metadatas = list(data.get("metadatas", []))
            self._embeddings = list(data.get("embeddings", []))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[rag] could not load {self._path.name}: {e}")

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ids": self._ids,
            "contents": self._contents,
            "metadatas": self._metadatas,
            "embeddings": self._embeddings,
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def count(self) -> int:
        return len(self._ids)

    def reset(self) -> None:
        self._ids, self._contents, self._metadatas, self._embeddings = [], [], [], []
        if self._path.exists():
            self._path.unlink()

    def add(
        self,
        ids: list[str],
        contents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        self._ids.extend(ids)
        self._contents.extend(contents)
        self._metadatas.extend(metadatas)
        self._embeddings.extend(embeddings)
        self._persist()

    def query(
        self,
        query_embedding: list[float],
        k: int,
        where: dict[str, Any] | None,
    ) -> list[tuple[str, str, dict[str, Any], float]]:
        if not self._ids:
            return []
        scored: list[tuple[int, float]] = []
        for i, emb in enumerate(self._embeddings):
            if where and not _matches_filter(self._metadatas[i], where):
                continue
            dist = 1.0 - _cosine(query_embedding, emb)
            scored.append((i, dist))
        scored.sort(key=lambda x: x[1])
        return [
            (self._ids[i], self._contents[i], self._metadatas[i], dist)
            for i, dist in scored[:k]
        ]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _matches_filter(meta: dict[str, Any], where: dict[str, Any]) -> bool:
    """Mimic a subset of Chroma's where clause: flat equality or $and."""
    if "$and" in where:
        return all(_matches_filter(meta, sub) for sub in where["$and"])
    return all(meta.get(k) == v for k, v in where.items())


class RAGEngine:
    """Retrieval backend (ChromaDB or in-memory) + Groq synthesis."""

    def __init__(self, country: str, collection_suffix: str = "v1") -> None:
        self.country = country
        self.collection_name = f"solar_{country.lower().replace(' ', '_')}_{collection_suffix}"
        self._backend = _InMemoryBackend(self.collection_name)
        self._groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    # -- Indexing --

    def index_country(self, profile: CountryProfile, replace: bool = True) -> int:
        """Index all documents from a country profile. Returns count indexed."""
        if replace:
            self._backend.reset()

        docs = iter_all_documents(profile)
        if not docs:
            return 0

        ids = [d.id for d in docs]
        contents = [self._doc_for_embedding(d) for d in docs]
        metadatas = [self._flatten_metadata(d) for d in docs]
        embeddings = [_hash_embed(c) for c in contents]
        self._backend.add(ids, contents, metadatas, embeddings)
        return len(ids)

    @staticmethod
    def _doc_for_embedding(doc: Document) -> str:
        """Construct embedding text that captures scope + dimension + content."""
        return (
            f"[Dimension: {doc.dimension}] "
            f"[Scope: {doc.scope}] "
            f"{doc.content}"
        )

    @staticmethod
    def _flatten_metadata(doc: Document) -> dict[str, Any]:
        """Chroma only accepts scalar metadata values. Serialize sources as string."""
        src_str = " | ".join(
            f"{s.organization}: {s.document} ({s.accessed}) <{s.url}>"
            for s in doc.sources
        )
        langs = sorted({detect_language(s.url, s.organization) for s in doc.sources})
        return {
            "id": doc.id,
            "dimension": doc.dimension,
            "scope": doc.scope,
            "confidence": doc.confidence,
            "last_verified": doc.last_verified,
            "sources": src_str,
            "source_languages": ",".join(langs),
        }

    # -- Retrieval --

    def retrieve(
        self,
        query: str,
        k: int = RETRIEVAL_TOP_K,
        dimension: str | None = None,
        scope: str | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve top-k documents with optional filters."""
        where: dict[str, Any] | None = None
        if dimension and scope:
            where = {"$and": [{"dimension": dimension}, {"scope": scope}]}
        elif dimension:
            where = {"dimension": dimension}
        elif scope:
            where = {"scope": scope}

        hits = self._backend.query(
            query_embedding=_hash_embed(query),
            k=k,
            where=where,
        )
        return [
            RetrievalResult(
                document_id=doc_id,
                content=content,
                metadata=metadata,
                distance=distance,
            )
            for doc_id, content, metadata, distance in hits
        ]

    # -- Generation --

    def chat(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        k: int = RETRIEVAL_TOP_K,
    ) -> ChatResponse:
        """Generate a grounded response. history is list of {role, content}."""
        if self._groq is None:
            return ChatResponse(
                answer="GROQ_API_KEY is not configured. Set it in .env to enable chat.",
                sources_used=(),
                retrieved_ids=(),
            )

        retrieved = self.retrieve(query, k=k)
        if not retrieved:
            return ChatResponse(
                answer=(
                    "I don't have verified data indexed for this query. "
                    "Either no documents were retrieved, or the knowledge base is empty. "
                    "Please confirm data has been ingested for this country."
                ),
                sources_used=(),
                retrieved_ids=(),
            )

        context = self._format_context(retrieved)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-6:])  # cap turns to bound token usage
        messages.append({
            "role": "user",
            "content": f"FACTS:\n{context}\n\nQUESTION: {query}\n\nAnswer from the FACTS above only.",
        })

        completion = self._groq.chat.completions.create(
            model=MODEL_SYNTHESIS,
            messages=messages,
            temperature=0.1,
            max_tokens=900,
        )
        answer = completion.choices[0].message.content or ""

        sources = tuple({
            "id": r.document_id,
            "scope": r.metadata.get("scope"),
            "dimension": r.metadata.get("dimension"),
            "confidence": r.metadata.get("confidence"),
            "verified": r.metadata.get("last_verified"),
            "sources": r.metadata.get("sources"),
        } for r in retrieved)

        return ChatResponse(
            answer=answer,
            sources_used=sources,
            retrieved_ids=tuple(r.document_id for r in retrieved),
        )

    @staticmethod
    def _format_context(results: list[RetrievalResult]) -> str:
        """Format retrieved chunks into a numbered context block."""
        blocks: list[str] = []
        for i, r in enumerate(results, 1):
            lang_field = r.metadata.get("source_languages") or ""
            codes = [c for c in lang_field.split(",") if c]
            if not codes:
                codes = detect_languages_from_sources_str(
                    str(r.metadata.get("sources") or "")
                )
            lang_line = ""
            non_en = [c for c in codes if c != "en"]
            if non_en:
                names = ", ".join(language_name(c) for c in non_en)
                lang_line = (
                    f"\nSourceLanguage: {names} "
                    f"[translation disclosure required in answer]"
                )
            blocks.append(
                f"[{i}] (scope: {r.metadata.get('scope')}, "
                f"dimension: {r.metadata.get('dimension')}, "
                f"confidence: {r.metadata.get('confidence')}, "
                f"verified: {r.metadata.get('last_verified')})\n"
                f"{r.content}\n"
                f"Sources: {r.metadata.get('sources')}"
                f"{lang_line}"
            )
        return "\n\n".join(blocks)
