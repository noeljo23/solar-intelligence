# PowerTrust Solar Intelligence


## What it does

- **Zero-hallucination RAG** over a curated 190+ document knowledge base covering 10 countries across LatAm, Africa, and Southeast Asia.
- **Multi-agent collection pipeline** (Collector → Validator → Synthesizer → Alternates → Auditor) that requires independent corroboration before any fact enters the KB.
- **Feasibility scoring** across 6 PowerTrust dimensions — cost & economics, grid access, subsidies & incentives, utility standards, public comment, unknown unknowns — with explicit data-imputation flags.
- **Translation-risk layer**: detects Portuguese, Spanish, Bahasa Indonesia, and Vietnamese primary sources and forces the LLM to disclose the translation hop in every affected answer.
- **HPC-scale collection** via SLURM on Northeastern's Explorer H200 nodes for parallel multi-source research.

## Supported countries

Brazil, Mexico, Indonesia, Vietnam, South Africa, Chile, Colombia, Nigeria, Kenya, Malaysia.

## Quick start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Set your Groq API key
cp .env.example .env
# edit .env and paste GROQ_API_KEY=...

# 3. Launch
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## Architecture

```
┌────────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  KB (JSON per      │───▶│  _InMemoryBackend    │───▶│  RAGEngine      │
│  country + audit)  │    │  (json + cosine,     │    │  + Groq LLM     │
└────────────────────┘    │  blake2b 384-dim)    │    └────────┬────────┘
                          └──────────────────────┘             │
                                                               ▼
┌────────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  HPC Collector     │───▶│  Validator + Audit   │───▶│  Synthesis +    │
│  (SLURM / H200)    │    │  (multi-agent)       │    │  Citations      │
└────────────────────┘    └──────────────────────┘    └─────────────────┘
```

### Why `_InMemoryBackend`?

ChromaDB 1.5.x segfaults on Windows during `collection.add()`. For a ~200-doc corpus, brute-force cosine over pre-computed 384-dim hash embeddings runs in under a millisecond — so we ship a pure-Python json + cosine backend and skip the segfault entirely. The backend is drop-in compatible with Chroma's query API (id/content/metadata/distance tuples, `$and` filters).

Set `SOLAR_RAG_BACKEND=memory` to force the memory backend (default on Windows).

## Repository layout

```
solar-intelligence/
├── app.py                        Streamlit entry point
├── config.py                     Countries, dimensions, model IDs, weights
├── requirements.txt
├── src/
│   ├── schema.py                 Frozen dataclasses for Source/Document/CountryProfile
│   ├── kb_loader.py              Loads + validates country_*.json files
│   ├── scoring.py                Feasibility scoring (0-100 per state)
│   ├── visualizations.py         Plotly charts (feasibility bar, radar, heatmap)
│   ├── views.py                  Streamlit view renderers
│   ├── rag_engine.py             In-memory retrieval + Groq chat
│   ├── data_collector.py         Collector + Validator agents
│   ├── audit.py                  Auditor agent (consistency + corroboration)
│   ├── kb_ingestor.py            HPC output → KB JSON
│   └── language.py               Translation-risk detection
├── data/
│   ├── knowledge_base/           country_*.json — the verified KB
│   └── collected/                HPC output (one dir per SLURM job)
├── hpc/
│   ├── run_collection.py         HPC entry (reads JSONL batch, writes JSONL per job)
│   ├── submit_collection.slurm   SLURM script for H200 partition
│   └── batches/                  Batch JSONL files grouping source pairs by dimension
└── tests/                        pytest suite (121 tests across core modules)
```

## Running tests

```bash
pytest tests/
pytest tests/ --cov=src --cov-report=term  # coverage report
```

**238 tests passing, 82% line coverage overall.**

| Module                | Coverage |
|-----------------------|----------|
| `language.py`         | 100%     |
| `scoring.py`          | 100%     |
| `visualizations.py`   | 100%     |
| `kb_loader.py`        | 98%      |
| `schema.py`           | 96%      |
| `audit.py`            | 94%      |
| `kb_ingestor.py`      | 84%      |
| `rag_engine.py`       | 81%      |
| `views.py`            | 76%      |
| `data_collector.py`   | 60%      |

LLM-dependent agents (`audit`, `data_collector`) are tested with `MagicMock`-patched Groq clients.
Streamlit views are covered by pure-function tests plus `streamlit.testing.v1.AppTest` smoke
tests that boot the full app against the real KB and exercise every sidebar view.

## HPC data collection

```bash
# On the Explorer head node:
cd ~/solar-intelligence
sbatch hpc/submit_collection.slurm hpc/batches/expansion_batch.jsonl

# Pull results back to laptop, then ingest:
python -m src.kb_ingestor --run-id <SLURM_JOB_ID>
```

Each batch line is `{country, state?, dimension, sources[]}` with 2+ independent sources per dimension to force corroboration. The auditor rejects any fact that does not reconcile across at least two sources.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `chromadb` segfault on Windows | chromadb 1.5.x HNSW + missing MSVC runtime | Default backend is now `_InMemoryBackend`; no action needed |
| `GROQ_API_KEY missing` banner | `.env` not present or empty | `cp .env.example .env` and paste your key |
| Country shows "coming soon" | `country_<Name>.json` not in `data/knowledge_base/` | Run HPC collection for that country or add a hand-curated KB file |
| Chat returns "I don't have verified data" | Retrieval found no matching docs | Broaden the query, or check that indexing ran (sidebar shows "Countries loaded") |

## Design choices worth knowing

1. **Frozen dataclasses everywhere.** `Source`, `Document`, `CountryProfile`, `FeasibilityScore`, `DimensionScore` all immutable. Every data transform returns a new instance — no hidden mutation.
2. **Every fact carries provenance.** `Source.url` must start with `http(s)://`; `Source.accessed` must be ISO date. Validation runs at load time and bad files are skipped with a log line, not silently ignored.
3. **Explicit imputation flags.** When a metric is missing, scoring uses a 50 neutral baseline *and* marks `imputed=True` so the dashboard can surface it rather than pretending the score is fully-informed.
4. **Translation disclosure is a system-prompt rule.** See `SYSTEM_PROMPT` rule #8 — whenever a retrieved source shows a non-English language, the LLM must append `"⚠ Translated from [language] — verify numbers against the original document."` This is tested end-to-end in the context-formatting layer.

## License

Hackathon project. Code released under MIT; data sources retain their original licenses (mostly government/regulator public-domain filings).
