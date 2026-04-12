"""
FastAPI layer wrapping the existing Python RAG stack for the Next.js frontend.

Design: pure HTTP facade — no business logic. Loads KB once at startup,
keeps one RAGEngine per country (rebuilt lazily).
"""
from __future__ import annotations

import os
import sys
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

from config import DIMENSION_LABELS, DIMENSIONS, KB_DIR
from src.kb_loader import load_all_countries
from src.rag_engine import RAGEngine
from src.scoring import score_country
from src.schema import CountryProfile, Document


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


def _country_rating(score: float) -> str:
    if score >= 80: return "Excellent"
    if score >= 65: return "Good"
    if score >= 50: return "Moderate"
    if score >= 35: return "Challenging"
    return "Poor"


# ---------- Schemas ----------

class ChatRequest(BaseModel):
    country: str
    message: str
    history: list[dict[str, str]] = []


class ChatResponseOut(BaseModel):
    answer: str
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
            "rating": _country_rating(avg),
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
