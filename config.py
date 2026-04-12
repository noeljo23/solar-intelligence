"""
Configuration for PowerTrust Solar Intelligence Platform.

Central config for models, countries, and system settings.
Secrets are loaded from environment variables only.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# -- Paths --
ROOT_DIR: Path = Path(__file__).parent
DATA_DIR: Path = ROOT_DIR / "data"
KB_DIR: Path = DATA_DIR / "knowledge_base"
CHROMA_DIR: Path = ROOT_DIR / ".chroma"

# -- Secrets (env only) --
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")

# -- Models --
# Large reasoning model for chat synthesis
MODEL_SYNTHESIS: str = "llama-3.3-70b-versatile"
# Fast model for validation / classification
MODEL_VALIDATOR: str = "llama-3.1-8b-instant"
# Model for data collection reasoning
MODEL_COLLECTOR: str = "llama-3.3-70b-versatile"

# -- RAG settings --
RETRIEVAL_TOP_K: int = 8
CHUNK_SIZE_CHARS: int = 1200
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # via chromadb default

# -- Six dimensions (per hackathon brief) --
DIMENSIONS: tuple[str, ...] = (
    "cost_economics",
    "grid_access",
    "subsidies_incentives",
    "utility_standards",
    "public_comment",
    "unknown_unknowns",
)

DIMENSION_LABELS: dict[str, str] = {
    "cost_economics": "Cost & Economics",
    "grid_access": "Grid Access & Queue Dynamics",
    "subsidies_incentives": "Subsidies, Incentives & Policy",
    "utility_standards": "Utility Standards & Obligations",
    "public_comment": "Public Comment & Approval Signals",
    "unknown_unknowns": "Unknown Unknowns",
}

# -- Supported countries (expand by adding a KB file) --
SUPPORTED_COUNTRIES: tuple[str, ...] = (
    "Mexico",
    "Brazil",
    "Indonesia",
    "Vietnam",
    "South Africa",
    "Malaysia",
    "Chile",
    "Colombia",
    "Nigeria",
    "Kenya",
)

# -- Feasibility scoring weights (sum must equal 1.0) --
SCORING_WEIGHTS: dict[str, float] = {
    "cost_economics": 0.25,
    "grid_access": 0.20,
    "subsidies_incentives": 0.20,
    "utility_standards": 0.15,
    "public_comment": 0.10,
    "unknown_unknowns": 0.10,
}

# -- Sanity check --
assert abs(sum(SCORING_WEIGHTS.values()) - 1.0) < 1e-9, "weights must sum to 1.0"
