"""
Data collection + validation pipeline.

Dual-agent architecture for zero-hallucination data ingestion:

    1. CollectorAgent  — given (country, state, dimension), searches web
                         and official regulator sources, extracts candidate
                         facts with their source text.
    2. ValidatorAgent  — independently re-reads the source text and confirms
                         the candidate fact is supported. If the source text
                         does not literally support the fact, it is REJECTED.
    3. Only accepted (fact, source) pairs are written to the KB.

This module is designed to run on HPC (see hpc/submit_collection.slurm).
It uses Groq API by default but can swap to local vLLM/Transformers for
offline validation on H200.
"""
from __future__ import annotations

import io
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import httpx
from groq import Groq

from config import GROQ_API_KEY, MODEL_COLLECTOR, MODEL_VALIDATOR
from src.audit import AuditReport, AuditorAgent, run_audit

# Optional PDF support. Pure-Python so it installs cleanly on HPC.
try:
    import pypdf  # type: ignore
    _PDF_OK = True
except ImportError:
    _PDF_OK = False


# Minimal HTML -> text stripper (avoids BS4 dep on HPC).
_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Strip HTML to readable text. Small, dependency-free."""
    if not html:
        return ""
    stripped = _SCRIPT_STYLE.sub(" ", html)
    stripped = _TAG.sub(" ", stripped)
    # Drop HTML entities (naive but adequate for LLM input)
    stripped = stripped.replace("&nbsp;", " ").replace("&amp;", "&")
    stripped = stripped.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return _WS.sub(" ", stripped).strip()


def pdf_to_text(pdf_bytes: bytes, max_pages: int = 40) -> str:
    """Extract text from a PDF. Scanned/image PDFs return empty — no OCR.

    Caps at max_pages to bound LLM input; regulatory docs beyond 40 pages
    are usually indexable by section anyway.
    """
    if not _PDF_OK or not pdf_bytes:
        return ""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
        return _WS.sub(" ", " ".join(parts)).strip()
    except Exception as e:  # noqa: BLE001 — pypdf raises various types, all recoverable
        print(f"[collector] pdf parse failed: {e}")
        return ""


_NO_FACT_MARKERS = (
    "no relevant",
    "no facts",
    "no quantitative",
    "not available",
    "cannot extract",
)


def _looks_like_empty_placeholder(fact_text: str, source_text: str) -> bool:
    """Collectors sometimes emit a placeholder fact when nothing is extractable.

    Filter those out rather than sending to validator.
    """
    if not fact_text or not source_text.strip():
        return True
    low = fact_text.lower()
    return any(m in low for m in _NO_FACT_MARKERS)


def _chunk_text(text: str, chunk_chars: int = 30_000, overlap: int = 1_500) -> list[str]:
    """Split long text into overlapping windows for chunked LLM processing.

    30K chars ~ 7.5K tokens — well within Llama 3.3 70B's 128K context but
    safe headroom for the prompt envelope + response budget.
    """
    if len(text) <= chunk_chars:
        return [text]
    chunks: list[str] = []
    step = chunk_chars - overlap
    for start in range(0, len(text), step):
        chunks.append(text[start:start + chunk_chars])
        if start + chunk_chars >= len(text):
            break
    return chunks


# -- Data types --

@dataclass(frozen=True)
class CandidateFact:
    """A fact proposed by CollectorAgent, awaiting validation."""
    fact: str
    source_text: str
    source_url: str
    source_organization: str
    source_document: str
    country: str
    state: str | None
    dimension: str
    data_points: dict[str, Any]


@dataclass(frozen=True)
class ValidationVerdict:
    accepted: bool
    reason: str
    confidence: str  # "high" | "medium" | "low"


# -- Prompt templates --

COLLECTOR_SYSTEM = """You are a rigorous energy-sector data collector for PowerTrust.

You receive a query about a specific (country, state, dimension) and source text retrieved from official regulatory / government websites. Your job:

1. Extract FACTS that the source text literally states.
2. Do NOT infer, estimate, or combine facts across sources.
3. Quote the relevant sentence(s) from the source verbatim in 'source_text'.
4. If the source does not contain relevant information about the dimension, return {"facts": []}.
5. Prefer quantitative facts (numbers, dates, percentages) with units.

CRITICAL FACT FORMAT — each 'fact' MUST be a COMPLETE self-contained assertion that
stands on its own without the source text. Never return a bare number, bare date,
bare year, or bare code as a fact.

BAD:  "482"
BAD:  "17 April 2012"
BAD:  "2020"
BAD:  "9"
GOOD: "ANEEL Resolution 482 was issued on 17 April 2012 and established net metering in Brazil."
GOOD: "The FiT under Decision 13/2020 expired on 31 December 2020."
GOOD: "NERSA is governed by nine members: five part-time and four full-time."

Each 'fact' must name the subject, the quantity, the unit/scope, and any date. A
reader seeing ONLY the fact string must understand what it asserts.

Output a single JSON object: {"facts": [ {fact, source_text, data_points}, ... ]}.
The data_points value must be an object (can be empty). Never output a list at
the top level.
"""

VALIDATOR_SYSTEM = """You are an independent data validator. You receive a CANDIDATE FACT and its claimed SOURCE TEXT.

Your job is adversarial: determine whether the source text LITERALLY supports the fact as stated.

Rules:
- If the fact contains a number not present in the source text, REJECT.
- If the fact generalizes beyond what the source says, REJECT.
- If the fact is temporally broader (e.g. 'currently' when source is dated), REJECT or require caveat.
- Only ACCEPT when the source text directly and unambiguously states the fact.

Output JSON: {accepted: bool, reason: str, confidence: 'high'|'medium'|'low'}
"""


SCOUT_SYSTEM = """You are a research scout for a solar-energy intelligence platform.

Given a (country, state_or_province, dimension), propose 3-6 AUTHORITATIVE URLs
from OFFICIAL government and regulator sources only. NO Wikipedia, NO news
outlets, NO blogs, NO aggregators.

Prefer in this order:
1. National energy regulator (e.g. ANEEL for Brazil, CRE for Mexico, MEMR for
   Indonesia, MOIT for Vietnam, NERSA for South Africa)
2. Grid operator / state utility (ONS, CENACE, PLN, EVN, Eskom)
3. Ministry of energy or treasury (for subsidies/tax)
4. Environmental agency (for public_comment dimension)
5. Law repositories (planalto.gov.br, jdih.esdm.go.id, vbpl.vn)

Each proposed URL must be on a .gov / .gov.br / .gob.mx / .gov.vn / .go.id / .co.za /
.gov.za / .org.za (NERSA) or equivalent official domain.

Output JSON: {"urls": [{"url", "organization", "document", "rationale"}]}
"""


SYNTHESIZER_SYSTEM = """You are a KB synthesizer for a solar intelligence platform.

You receive a set of VALIDATED facts (each already source-cited and independently
verified). Your job: assemble them into a single KB Document.

Rules:
- Every sentence in the prose MUST be traceable to one or more of the input facts.
- Do NOT introduce numbers, dates, or claims not present in the input facts.
- If two facts conflict, say so explicitly and cite both.
- Keep prose tight, 2-4 sentences. Prefer quantitative language.
- Populate data_points ONLY with values that appear in input facts.

Output JSON: {"content": str, "data_points": object, "confidence": "high|medium|low"}
"""


# -- Agents --

class CollectorAgent:
    """Retrieves source text and proposes candidate facts."""

    def __init__(self, groq_client: Groq | None = None) -> None:
        self._groq = groq_client or (Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None)

    def fetch_url(self, url: str, timeout: float = 30.0) -> str:
        """Fetch URL and return readable text. Handles HTML and PDF.

        Returns empty string on failure. Browser-like User-Agent to bypass
        gov portals that block default UAs. PDFs are parsed via pypdf when
        available; scanned/image PDFs return empty (no OCR — that's honest).
        """
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout,
                headers={
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/pdf,application/json",
                    "Accept-Language": "en,*;q=0.5",
                },
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "").lower()
                body_bytes = resp.content
                body_text = resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            print(f"[collector] fetch failed {url}: {e}")
            return ""

        is_pdf = "pdf" in ctype or url.lower().endswith(".pdf") or body_bytes[:4] == b"%PDF"
        if is_pdf:
            text = pdf_to_text(body_bytes)
            if not text:
                print(f"[collector] empty PDF text (likely scanned/image): {url}")
        elif "<" in body_text[:200]:
            text = html_to_text(body_text)
        else:
            text = body_text
        return text[:50_000]  # cap to bound token usage

    def propose_facts(
        self,
        country: str,
        state: str | None,
        dimension: str,
        source_url: str,
        source_organization: str,
        source_document: str,
        source_text: str,
    ) -> list[CandidateFact]:
        """LLM extracts candidate facts from source_text.

        Long sources are chunked so we exploit Llama 3.3 70B's full 128K context
        without truncating rich regulatory PDFs. Chunks are processed in parallel
        against Groq, and deduplicated in-process.
        """
        if self._groq is None or not source_text:
            return []

        chunks = _chunk_text(source_text, chunk_chars=30_000, overlap=1_500)
        scope = f"state: {state}" if state else "national"

        def _one_chunk(chunk: str, idx: int) -> list[dict]:
            user = (
                f"COUNTRY: {country}\n"
                f"SCOPE: {scope}\n"
                f"DIMENSION: {dimension}\n"
                f"SOURCE: {source_organization} - {source_document}\n"
                f"URL: {source_url}\n"
                f"CHUNK: {idx + 1} of {len(chunks)}\n\n"
                f"SOURCE TEXT:\n{chunk}\n\n"
                f"Extract every concrete, quantitative fact in this chunk that is relevant to "
                f"DIMENSION for this SCOPE. Each fact must be a self-contained assertion.\n"
                f"Return JSON object: {{\"facts\": [...]}}"
            )
            try:
                resp = self._groq.chat.completions.create(
                    model=MODEL_COLLECTOR,
                    messages=[
                        {"role": "system", "content": COLLECTOR_SYSTEM},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.0,
                    max_tokens=2500,
                    response_format={"type": "json_object"},
                )
                parsed = json.loads(resp.choices[0].message.content or "{}")
                raw = parsed.get("facts") or parsed.get("data") or []
                if isinstance(raw, dict):
                    raw = [raw]
                return list(raw)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[collector] parse failure chunk {idx}: {e}")
                return []

        raw_facts: list[dict] = []
        if len(chunks) == 1:
            raw_facts = _one_chunk(chunks[0], 0)
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as pool:
                for chunk_facts in pool.map(lambda p: _one_chunk(p[1], p[0]), enumerate(chunks)):
                    raw_facts.extend(chunk_facts)

        seen_facts: set[str] = set()
        candidates: list[CandidateFact] = []
        for rf in raw_facts:
            if not isinstance(rf, dict) or "fact" not in rf:
                continue
            fact_text = str(rf["fact"]).strip()
            source_excerpt = str(rf.get("source_text", ""))[:2000]
            if _looks_like_empty_placeholder(fact_text, source_excerpt):
                continue
            dedup_key = fact_text.lower()[:120]
            if dedup_key in seen_facts:
                continue
            seen_facts.add(dedup_key)
            candidates.append(CandidateFact(
                fact=fact_text,
                source_text=source_excerpt,
                source_url=source_url,
                source_organization=source_organization,
                source_document=source_document,
                country=country,
                state=state,
                dimension=dimension,
                data_points=rf.get("data_points", {}) if isinstance(rf.get("data_points"), dict) else {},
            ))
        return candidates


class ValidatorAgent:
    """Adversarial validator: only accepts facts literally supported by source."""

    def __init__(self, groq_client: Groq | None = None) -> None:
        self._groq = groq_client or (Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None)

    def validate(self, candidate: CandidateFact) -> ValidationVerdict:
        """Independently check that source_text supports the fact."""
        if self._groq is None:
            return ValidationVerdict(False, "GROQ_API_KEY not set", "low")
        if not candidate.source_text.strip():
            return ValidationVerdict(False, "empty source_text", "low")

        user = (
            f"CANDIDATE FACT: {candidate.fact}\n\n"
            f"SOURCE TEXT:\n{candidate.source_text}\n\n"
            f"Does the SOURCE TEXT literally support the CANDIDATE FACT? "
            f"Reply with JSON {{accepted, reason, confidence}}."
        )
        try:
            resp = self._groq.chat.completions.create(
                model=MODEL_VALIDATOR,
                messages=[
                    {"role": "system", "content": VALIDATOR_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content or "{}")
            return ValidationVerdict(
                accepted=bool(parsed.get("accepted", False)),
                reason=str(parsed.get("reason", ""))[:500],
                confidence=str(parsed.get("confidence", "low")),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return ValidationVerdict(False, f"validator error: {e}", "low")


class ScoutAgent:
    """Proposes authoritative gov/regulator URLs for a (country, state, dimension) query.

    Runs before Collector. Output feeds into batch files for HPC collection.
    """

    def __init__(self, groq_client: Groq | None = None) -> None:
        self._groq = groq_client or (Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None)

    def propose_urls(
        self,
        country: str,
        state: str | None,
        dimension: str,
    ) -> list[dict[str, str]]:
        """Ask LLM for authoritative URLs. Returns list of {url, organization, document, rationale}."""
        if self._groq is None:
            return []
        scope = f"state/province: {state}" if state else "national"
        user = (
            f"COUNTRY: {country}\nSCOPE: {scope}\nDIMENSION: {dimension}\n\n"
            f"Propose 3-6 authoritative URLs. Gov/regulator ONLY. Output {{\"urls\": [...]}}."
        )
        try:
            resp = self._groq.chat.completions.create(
                model=MODEL_COLLECTOR,
                messages=[
                    {"role": "system", "content": SCOUT_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=800,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content or "{}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[scout] parse failure: {e}")
            return []
        urls = parsed.get("urls") or []
        if not isinstance(urls, list):
            return []
        out: list[dict[str, str]] = []
        for item in urls:
            if not isinstance(item, dict) or "url" not in item:
                continue
            u = str(item["url"])
            if not (u.startswith("http://") or u.startswith("https://")):
                continue
            out.append({
                "url": u,
                "organization": str(item.get("organization", "")),
                "document": str(item.get("document", "")),
                "rationale": str(item.get("rationale", "")),
            })
        return out


class SynthesizerAgent:
    """Given validated facts, produces a KB Document (prose + data_points)."""

    def __init__(self, groq_client: Groq | None = None) -> None:
        self._groq = groq_client or (Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None)

    def synthesize(
        self,
        country: str,
        state: str | None,
        dimension: str,
        accepted_facts: list[CandidateFact],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Return {content, data_points, confidence}. Every prose claim traces to accepted_facts.

        Default temperature=0.0 for the primary (reference) draft. Higher
        temperatures are used for alternate drafts in the consistency check.
        """
        if self._groq is None or not accepted_facts:
            return {"content": "", "data_points": {}, "confidence": "low"}
        facts_blob = "\n".join(
            f"- [{i + 1}] {f.fact}  (source: {f.source_organization} - {f.source_document}; data_points={f.data_points})"
            for i, f in enumerate(accepted_facts)
        )
        scope = f"state/province: {state}" if state else "national"
        user = (
            f"COUNTRY: {country}\nSCOPE: {scope}\nDIMENSION: {dimension}\n\n"
            f"VALIDATED FACTS (every output sentence MUST trace to one of these):\n{facts_blob}\n\n"
            f"Synthesize a KB document. Output JSON {{content, data_points, confidence}}."
        )
        try:
            resp = self._groq.chat.completions.create(
                model=MODEL_COLLECTOR,
                messages=[
                    {"role": "system", "content": SYNTHESIZER_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content or "{}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[synth] parse failure: {e}")
            return {"content": "", "data_points": {}, "confidence": "low"}
        return {
            "content": str(parsed.get("content", "")),
            "data_points": parsed.get("data_points", {}) if isinstance(parsed.get("data_points"), dict) else {},
            "confidence": str(parsed.get("confidence", "medium")),
        }

    def draft_alternates(
        self,
        country: str,
        state: str | None,
        dimension: str,
        accepted_facts: list[CandidateFact],
        temperatures: tuple[float, ...] = (0.3, 0.6),
    ) -> list[str]:
        """Generate alternate drafts at higher temperatures for SelfCheckGPT-style audit.

        Alternates are drawn from the same validated-facts pool — they are not
        intended to introduce new claims, only to paraphrase. Claims that appear
        in the primary but not in alternates are a hallucination signal.
        Runs in parallel to avoid serial latency cost.
        """
        if self._groq is None or not accepted_facts or not temperatures:
            return []
        from concurrent.futures import ThreadPoolExecutor

        def _one(t: float) -> str:
            draft = self.synthesize(country, state, dimension, accepted_facts, temperature=t)
            return str(draft.get("content", ""))

        with ThreadPoolExecutor(max_workers=min(len(temperatures), 4)) as pool:
            alternates = list(pool.map(_one, temperatures))
        return [a for a in alternates if a.strip()]


# -- Pipeline orchestration --

@dataclass
class PipelineResult:
    accepted: list[tuple[CandidateFact, ValidationVerdict]]
    rejected: list[tuple[CandidateFact, ValidationVerdict]]
    synthesized: dict[str, Any]
    audit: dict[str, Any]


def run_pipeline(
    country: str,
    state: str | None,
    dimension: str,
    sources: list[dict[str, str]],
    output_path: Path | None = None,
    max_validator_workers: int = 8,
    audit_enabled: bool = True,
    alternate_temperatures: tuple[float, ...] = (0.3, 0.6),
) -> PipelineResult:
    """Full 5-stage pipeline: Collector -> Validator -> Synthesizer -> Alternates -> Auditor.

    Validator runs concurrently — Groq can handle burst QPS, so serial sleep
    throttling is an unnecessary tax. Alternate drafts also run in parallel.
    The auditor applies three orthogonal checks (corroboration, citation
    integrity, self-consistency); see src/audit.py for methodology references.
    """
    from concurrent.futures import ThreadPoolExecutor

    collector = CollectorAgent()
    validator = ValidatorAgent()
    synthesizer = SynthesizerAgent()

    all_candidates: list[CandidateFact] = []
    for src in sources:
        text = collector.fetch_url(src["url"])
        if not text:
            continue
        all_candidates.extend(collector.propose_facts(
            country=country,
            state=state,
            dimension=dimension,
            source_url=src["url"],
            source_organization=src["organization"],
            source_document=src["document"],
            source_text=text,
        ))

    accepted: list[tuple[CandidateFact, ValidationVerdict]] = []
    rejected: list[tuple[CandidateFact, ValidationVerdict]] = []

    if all_candidates:
        with ThreadPoolExecutor(max_workers=max_validator_workers) as pool:
            verdicts = list(pool.map(validator.validate, all_candidates))
        for cand, verdict in zip(all_candidates, verdicts):
            if verdict.accepted:
                accepted.append((cand, verdict))
            else:
                rejected.append((cand, verdict))

    accepted_facts = [c for c, _ in accepted]
    synthesized = synthesizer.synthesize(
        country=country,
        state=state,
        dimension=dimension,
        accepted_facts=accepted_facts,
    )

    audit_dict: dict[str, Any] = {}
    if audit_enabled and synthesized.get("content") and accepted_facts:
        alternates = synthesizer.draft_alternates(
            country=country,
            state=state,
            dimension=dimension,
            accepted_facts=accepted_facts,
            temperatures=alternate_temperatures,
        )
        report: AuditReport = run_audit(
            primary_content=str(synthesized["content"]),
            alternate_contents=alternates,
            accepted_facts=[(c.fact, c.source_url) for c in accepted_facts],
            auditor=AuditorAgent(),
        )
        audit_dict = report.to_dict()

    result = PipelineResult(
        accepted=accepted,
        rejected=rejected,
        synthesized=synthesized,
        audit=audit_dict,
    )
    if output_path:
        _persist_result(result, output_path)
    return result


def _persist_result(result: PipelineResult, path: Path) -> None:
    """Write pipeline output as JSONL for auditability.

    Order: accepted facts, rejected facts, synthesis, audit report.
    Downstream consumers can stream the file and treat each status tag as a
    discrete row type.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for cf, v in result.accepted:
            f.write(json.dumps({"status": "accepted", "fact": asdict(cf), "verdict": asdict(v)}) + "\n")
        for cf, v in result.rejected:
            f.write(json.dumps({"status": "rejected", "fact": asdict(cf), "verdict": asdict(v)}) + "\n")
        if result.synthesized.get("content"):
            f.write(json.dumps({"status": "synthesis", "synthesis": result.synthesized}) + "\n")
        if result.audit:
            f.write(json.dumps({"status": "audit", "audit": result.audit}) + "\n")
