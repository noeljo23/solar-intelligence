"""
FastAPI layer wrapping the existing Python RAG stack for the Next.js frontend.

Design: pure HTTP facade — no business logic. Loads KB once at startup,
keeps one RAGEngine per country (rebuilt lazily).
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Allow running from repo root (python -m uvicorn api.main:app)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure user site-packages (where --user installs land under Anaconda) is importable.
import site
_user_site = site.getusersitepackages()
if _user_site and _user_site not in sys.path:
    sys.path.insert(0, _user_site)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import DIMENSION_LABELS, DIMENSIONS, KB_DIR, GROQ_API_KEY, MODEL_SYNTHESIS
from src.kb_loader import load_all_countries
from src.rag_engine import RAGEngine, SYSTEM_PROMPT
from src.scoring import rating_from_score, score_country
from src.schema import CountryProfile, Document

from groq import Groq

# Tuning knobs for the global-chat retrieval budget.
_RETRIEVAL_BUDGET = 18
_MIN_DOCS_PER_COUNTRY = 3
_MAX_DOCS_PER_COUNTRY = 6
_RETRIEVAL_POOL = ThreadPoolExecutor(max_workers=10)

# One Groq client for the process — avoids per-request connection-pool churn.
_groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


app = FastAPI(title="PowerTrust Solar Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- State ----------

_profiles: dict[str, CountryProfile] = {}
_engines: dict[str, RAGEngine] = {}


@app.on_event("startup")
def _startup() -> None:
    global _profiles
    _profiles = load_all_countries(Path(KB_DIR))
    # Pre-warm RAG engines to keep first-request latency low.
    for name in _profiles:
        _get_engine(name)


def _get_profile(name: str) -> CountryProfile:
    profile = _profiles.get(name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Unknown country: {name}")
    return profile


def _get_engine(name: str) -> RAGEngine:
    engine = _engines.get(name)
    if engine is None:
        profile = _get_profile(name)
        engine = RAGEngine(country=name)
        engine.index_country(profile)
        _engines[name] = engine
    return engine


# ---------- Schemas ----------

class ChatRequest(BaseModel):
    country: str
    message: str
    history: list[dict[str, str]] = []


class ChatResponseOut(BaseModel):
    answer: str
    sources: list[dict[str, Any]]


class GlobalChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class GlobalChatResponseOut(BaseModel):
    answer: str
    countries_used: list[str]
    sources: list[dict[str, Any]]


# ---------- Routes ----------

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "countries_loaded": len(_profiles),
        "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
    }


@app.get("/api/dimensions")
def dimensions() -> list[dict[str, str]]:
    return [{"key": k, "label": DIMENSION_LABELS[k]} for k in DIMENSIONS]


@app.get("/api/countries")
def countries() -> list[dict[str, Any]]:
    """Cross-country summary for landing page / comparison view."""
    out: list[dict[str, Any]] = []
    for name, p in _profiles.items():
        scores = score_country(name, p.states)
        if not scores:
            out.append({
                "name": name,
                "iso_code": p.iso_code,
                "regulator": p.regulator,
                "avg_score": None,
                "rating": None,
                "states_scored": 0,
                "documents": len(p.national_documents) + sum(len(s.documents) for s in p.states),
                "completeness": 0.0,
            })
            continue
        avg = round(sum(s.total_score for s in scores) / len(scores), 1)
        out.append({
            "name": name,
            "iso_code": p.iso_code,
            "regulator": p.regulator,
            "avg_score": avg,
            "rating": rating_from_score(avg),
            "states_scored": len(scores),
            "documents": len(p.national_documents) + sum(len(s.documents) for s in p.states),
            "completeness": round(
                sum(s.data_completeness_pct for s in scores) / len(scores), 1
            ),
        })
    return out


@app.get("/api/country/{name}")
def country_profile(name: str) -> dict[str, Any]:
    profile = _get_profile(name)
    return _profile_to_dict(profile)


@app.get("/api/country/{name}/scores")
def country_scores(name: str) -> list[dict[str, Any]]:
    profile = _get_profile(name)
    scores = score_country(name, profile.states)
    return [asdict(s) for s in scores]


@app.get("/api/country/{name}/audit")
def country_audit(name: str) -> dict[str, Any]:
    profile = _get_profile(name)
    hpc_count = sum(1 for s in profile.states for d in s.documents if _is_hpc_doc(d)) + \
        sum(1 for d in profile.national_documents if _is_hpc_doc(d))
    total_docs = sum(len(s.documents) for s in profile.states) + len(profile.national_documents)

    coverage_rows = []
    for s in profile.states:
        by_dim: dict[str, int] = {}
        for d in s.documents:
            by_dim[d.dimension] = by_dim.get(d.dimension, 0) + 1
        coverage_rows.append({"name": s.name, "by_dimension": by_dim})

    return {
        "country": name,
        "states": len(profile.states),
        "documents_total": total_docs,
        "documents_national": len(profile.national_documents),
        "documents_hpc": hpc_count,
        "coverage": coverage_rows,
        "audit": profile.data_audit,
        "hpc_audit": (profile.coverage_summary or {}).get("hpc_audit"),
    }


@app.post("/api/chat", response_model=ChatResponseOut)
def chat(req: ChatRequest) -> ChatResponseOut:
    engine = _get_engine(req.country)
    response = engine.chat(req.message, history=req.history)
    return ChatResponseOut(
        answer=response.answer,
        sources=[dict(s) for s in response.sources_used],
    )


# ---------- Global (cross-country) chat ----------

# Nicknames and spelling variants not derivable from profile name/iso code.
_NICKNAMES: dict[str, str] = {
    "brasil": "Brazil",
    "viet nam": "Vietnam",
    "rsa": "South Africa",
}

_alias_cache: dict[str, str] = {}
_aliases_by_length: list[tuple[str, str]] = []  # (alias, country), longest first


def _aliases() -> dict[str, str]:
    """Lowercase alias -> canonical country name, derived from loaded profiles."""
    if _alias_cache:
        return _alias_cache
    for name, p in _profiles.items():
        _alias_cache[name.lower()] = name
        if p.iso_code:
            _alias_cache[p.iso_code.lower()] = name
    for alias, name in _NICKNAMES.items():
        if name in _profiles:
            _alias_cache[alias] = name
    # Longest alias first so "south africa" wins over "africa".
    _aliases_by_length.extend(
        sorted(_alias_cache.items(), key=lambda kv: len(kv[0]), reverse=True)
    )
    return _alias_cache


def _detect_countries(message: str) -> list[str]:
    """Return country names mentioned in the message, preserving order."""
    cleaned = "".join(c if c.isalnum() or c == "." else " " for c in message.lower())
    text = f" {cleaned} "
    if not _aliases_by_length:
        _aliases()
    hits: list[str] = []
    seen: set[str] = set()
    for alias, country in _aliases_by_length:
        if f" {alias} " in text and country not in seen:
            seen.add(country)
            hits.append(country)
    return hits


def _countries_from_history(history: list[dict[str, str]]) -> list[str]:
    """Countries mentioned in recent turns, most recent first. Follow-ups
    like 'how do we solve this?' inherit scope from the prior turn."""
    hits: list[str] = []
    seen: set[str] = set()
    for msg in reversed(history or []):
        for c in _detect_countries(msg.get("content") or ""):
            if c not in seen:
                seen.add(c)
                hits.append(c)
    return hits


def _retrieval_query(message: str, history: list[dict[str, str]]) -> str:
    """Concatenate the last user turn with the current message so pronoun
    follow-ups ('how do we solve this?') still retrieve topical docs."""
    last_user = next(
        (m["content"] for m in reversed(history or []) if m.get("role") == "user"),
        "",
    )
    return f"{last_user}\n{message}" if last_user else message


@app.post("/api/chat-global", response_model=GlobalChatResponseOut)
def chat_global(req: GlobalChatRequest) -> GlobalChatResponseOut:
    if _groq_client is None:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    mentioned = _detect_countries(req.message)
    inherited = not mentioned and bool(req.history)
    if inherited:
        mentioned = _countries_from_history(req.history)
    targets = mentioned if mentioned else list(_profiles.keys())

    per_country = max(
        _MIN_DOCS_PER_COUNTRY,
        min(_MAX_DOCS_PER_COUNTRY, _RETRIEVAL_BUDGET // max(1, len(targets))),
    )
    query = _retrieval_query(req.message, req.history) if inherited else req.message

    def _retrieve(country: str) -> tuple[str, list[Any]]:
        return country, _get_engine(country).retrieve(query, k=per_country)

    retrieved = list(_RETRIEVAL_POOL.map(_retrieve, targets))

    blocks: list[str] = []
    used_sources: list[dict[str, Any]] = []
    i = 1
    for country, hits in retrieved:
        for r in hits:
            blocks.append(
                f"[{i}] (country: {country}, scope: {r.metadata.get('scope')}, "
                f"dimension: {r.metadata.get('dimension')}, "
                f"confidence: {r.metadata.get('confidence')}, "
                f"verified: {r.metadata.get('last_verified')})\n"
                f"{r.content}\n"
                f"Sources: {r.metadata.get('sources')}"
            )
            used_sources.append({
                "country": country,
                "id": r.document_id,
                "scope": r.metadata.get("scope"),
                "dimension": r.metadata.get("dimension"),
                "confidence": r.metadata.get("confidence"),
                "verified": r.metadata.get("last_verified"),
                "sources": r.metadata.get("sources"),
            })
            i += 1

    if not blocks:
        return GlobalChatResponseOut(
            answer="No verified data found in the knowledge base for this query.",
            countries_used=targets,
            sources=[],
        )

    context = "\n\n".join(blocks)
    scope_hint = (
        f"Scope for this question: {', '.join(targets)}."
        if mentioned else
        "Scope: no country was named. Answer from the available data only and attribute every fact to its country."
    )
    system_msg = SYSTEM_PROMPT + "\n\nWhen facts span multiple countries, label every fact with its country and never mix jurisdictions."

    messages: list[dict[str, str]] = [{"role": "system", "content": system_msg}]
    if req.history:
        messages.extend(req.history[-6:])
    messages.append({
        "role": "user",
        "content": f"{scope_hint}\n\nFACTS:\n{context}\n\nQUESTION: {req.message}\n\nAnswer from the FACTS above only.",
    })

    completion = _groq_client.chat.completions.create(
        model=MODEL_SYNTHESIS,
        messages=messages,
        temperature=0.1,
        max_tokens=900,
    )
    answer = completion.choices[0].message.content or ""

    return GlobalChatResponseOut(
        answer=answer,
        countries_used=targets,
        sources=used_sources,
    )


# ---------- Helpers ----------

def _is_hpc_doc(doc: Document) -> bool:
    return "_HPC_" in doc.id or "hpc" in doc.id.lower()


def _doc_to_dict(doc: Document) -> dict[str, Any]:
    return {
        "id": doc.id,
        "dimension": doc.dimension,
        "scope": doc.scope,
        "content": doc.content,
        "confidence": doc.confidence,
        "last_verified": doc.last_verified,
        "sources": [asdict(s) for s in doc.sources],
        "data_points": doc.data_points,
        "is_hpc": _is_hpc_doc(doc),
    }


def _profile_to_dict(profile: CountryProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "iso_code": profile.iso_code,
        "currency": profile.currency,
        "exchange_rate_to_usd": profile.exchange_rate_to_usd,
        "regulator": profile.regulator,
        "grid_operator": profile.grid_operator,
        "last_updated": profile.last_updated,
        "national_documents": [_doc_to_dict(d) for d in profile.national_documents],
        "states": [
            {
                "name": s.name,
                "iso_code": s.iso_code,
                "metrics": asdict(s.metrics),
                "documents": [_doc_to_dict(d) for d in s.documents],
                "data_completeness_pct": s.data_completeness_pct,
            }
            for s in profile.states
        ],
        "coverage_summary": profile.coverage_summary,
        "data_audit": profile.data_audit,
    }
