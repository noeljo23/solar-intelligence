"""
Post-validation audit: corroboration, citation integrity, consistency sampling.

Three peer-reviewed methodologies, one pass:

  1. Cross-source corroboration (Consensus.app) — validated facts asserting the
     same claim across >=2 distinct source URLs are flagged as corroborated.
  2. Citation integrity (Harvey AI / CoCounsel) — every sentence in the
     synthesized document must trace to one or more validated facts, or it is
     reported as unsupported (a hallucination signal).
  3. Self-consistency (SelfCheckGPT, Manakul et al. 2023) — a low-temperature
     reference synthesis is re-drafted at higher temperatures; claims that do
     not appear in the alternates receive a low consistency score.

The Auditor does NOT mutate the synthesis — it returns an immutable AuditReport
that downstream consumers (UI, scoring) can surface or use to gate claims.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from groq import Groq

from config import GROQ_API_KEY, MODEL_VALIDATOR

# Sentence splitter: split on .!? boundary followed by capital/digit/quote.
# Simple, dependency-free, and adequate for LLM-authored prose.
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=["\'(\[]?[A-Z0-9])')


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Returns [] for empty input."""
    stripped = (text or "").strip()
    if not stripped:
        return []
    parts = _SENT_SPLIT.split(stripped)
    return [p.strip() for p in parts if p.strip()]


CORROBORATION_SYSTEM = """You cluster VALIDATED facts into groups where each group asserts the SAME underlying claim, possibly in different words or citing different sources.

Rules:
- Two facts belong in the same cluster ONLY if they assert the same quantity, date, policy, or scope about the same subject.
- Facts with different numeric values (e.g. 4.5 GW vs 5.2 GW) belong to DIFFERENT clusters even if phrased similarly.
- A fact can belong to exactly one cluster.
- Single facts that share no claim with any other fact are their own cluster.

Input: a numbered list of facts, each prefixed with its 1-based index.
Output JSON: {"clusters": [[idx, ...], [idx, ...], ...]} where each inner list is the 1-based indices of facts in one cluster. Every input index must appear in exactly one cluster.
"""


CITATION_SYSTEM = """You audit whether each sentence of a synthesized document is supported by one or more of a list of VALIDATED facts.

Rules:
- A sentence is SUPPORTED if its numeric claims, dates, names, and policy assertions are all present (verbatim or as faithful paraphrase) in at least one cited fact.
- A sentence that adds information not present in any cited fact is UNSUPPORTED — return an empty list for that sentence.
- Do NOT use world knowledge. Only use the facts provided.

Output JSON: {"citations": [[idx, ...], [idx, ...], ...]}
One list per input sentence, in order. Empty list means the sentence is unsupported (hallucinated).
"""


CONSISTENCY_SYSTEM = """You check whether each PRIMARY sentence is echoed by each ALTERNATE draft.

Rules:
- A primary sentence is ECHOED by an alternate if the alternate contains the same core numeric claim, date, or policy assertion (paraphrase allowed).
- If the alternate omits or contradicts the primary sentence's claim, it is NOT echoed.

Output JSON: {"supports": [[bool, bool, ...], [bool, bool, ...], ...]}
Outer list has one entry per primary sentence, inner list has one boolean per alternate draft (in the order given).
"""


@dataclass(frozen=True)
class FactClaim:
    """Input to the auditor: a validated fact with its source URL for corroboration."""
    idx: int  # 1-based
    text: str
    source_url: str


@dataclass(frozen=True)
class AuditReport:
    """Immutable audit output. All indices are 1-based to match LLM output."""
    clusters: list[list[int]]
    corroboration_count: list[int]
    corroborated_flags: list[bool]
    sentences: list[str]
    citations: list[list[int]]
    unsupported_sentence_indices: list[int]
    alternate_contents: list[str]
    consistency_support: list[int]
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clusters": self.clusters,
            "corroboration_count": self.corroboration_count,
            "corroborated_flags": self.corroborated_flags,
            "sentences": self.sentences,
            "citations": self.citations,
            "unsupported_sentence_indices": self.unsupported_sentence_indices,
            "alternate_contents": self.alternate_contents,
            "consistency_support": self.consistency_support,
            "issues": self.issues,
        }


def _empty_report(sentences: list[str], n_alternates: int) -> AuditReport:
    """Safe fallback when the auditor can't run (missing key, empty inputs, etc.)."""
    return AuditReport(
        clusters=[],
        corroboration_count=[],
        corroborated_flags=[],
        sentences=sentences,
        citations=[[] for _ in sentences],
        unsupported_sentence_indices=list(range(len(sentences))),
        alternate_contents=[],
        consistency_support=[0] * len(sentences),
        issues=["auditor unavailable"],
    )


class AuditorAgent:
    """Runs corroboration + citation + consistency checks against validated facts."""

    def __init__(self, groq_client: Groq | None = None) -> None:
        self._groq = groq_client or (Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None)

    def _call(self, system: str, user: str, max_tokens: int) -> dict[str, Any] | None:
        if self._groq is None:
            return None
        try:
            resp = self._groq.chat.completions.create(
                model=MODEL_VALIDATOR,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[audit] parse failure: {e}")
            return None

    def corroborate(self, facts: list[FactClaim]) -> tuple[list[list[int]], list[int]]:
        """Cluster facts asserting the same claim.

        Returns (clusters, corroboration_count) where corroboration_count[i] is
        the number of DISTINCT source_urls in the cluster containing facts[i].
        """
        if not facts:
            return ([], [])
        blob = "\n".join(f"[{f.idx}] {f.text}" for f in facts)
        parsed = self._call(
            CORROBORATION_SYSTEM,
            f"FACTS:\n{blob}\n\nCluster facts asserting the same claim.",
            max_tokens=800,
        )
        if parsed is None:
            clusters = [[f.idx] for f in facts]
        else:
            raw = parsed.get("clusters") or []
            clusters = [
                [int(i) for i in c if isinstance(i, (int, float))]
                for c in raw
                if isinstance(c, list) and c
            ]
            clusters = [c for c in clusters if c]

        idx_to_url = {f.idx: f.source_url for f in facts}
        idx_to_cluster: dict[int, list[int]] = {}
        for cluster in clusters:
            for i in cluster:
                idx_to_cluster[i] = cluster

        counts: list[int] = []
        for f in facts:
            cluster = idx_to_cluster.get(f.idx, [f.idx])
            distinct_urls = {idx_to_url.get(i) for i in cluster if idx_to_url.get(i)}
            counts.append(len(distinct_urls))
        return clusters, counts

    def audit_citations(
        self,
        sentences: list[str],
        facts: list[FactClaim],
    ) -> tuple[list[list[int]], list[int]]:
        """Return (citations, unsupported_indices) for each sentence (0-based indices)."""
        if not sentences:
            return ([], [])
        if not facts:
            return ([[] for _ in sentences], list(range(len(sentences))))
        facts_blob = "\n".join(f"[{f.idx}] {f.text}" for f in facts)
        sents_blob = "\n".join(f"({i + 1}) {s}" for i, s in enumerate(sentences))
        parsed = self._call(
            CITATION_SYSTEM,
            f"FACTS:\n{facts_blob}\n\nSENTENCES:\n{sents_blob}\n\n"
            f"For each sentence return list of supporting fact indices.",
            max_tokens=800,
        )
        if parsed is None:
            return ([[] for _ in sentences], list(range(len(sentences))))
        raw_cites = parsed.get("citations") or []
        citations: list[list[int]] = []
        for i in range(len(sentences)):
            if i < len(raw_cites) and isinstance(raw_cites[i], list):
                cleaned = [int(x) for x in raw_cites[i] if isinstance(x, (int, float))]
            else:
                cleaned = []
            citations.append(cleaned)
        unsupported = [i for i, c in enumerate(citations) if not c]
        return citations, unsupported

    def consistency_check(
        self,
        primary_sentences: list[str],
        alternate_contents: list[str],
    ) -> list[int]:
        """For each primary sentence, return count of alternates that echo it."""
        if not primary_sentences or not alternate_contents:
            return [0] * len(primary_sentences)
        prim_blob = "\n".join(f"({i + 1}) {s}" for i, s in enumerate(primary_sentences))
        alt_blob = "\n\n---\n\n".join(
            f"[ALT {j + 1}]\n{a}" for j, a in enumerate(alternate_contents)
        )
        parsed = self._call(
            CONSISTENCY_SYSTEM,
            f"PRIMARY SENTENCES:\n{prim_blob}\n\nALTERNATE DRAFTS:\n{alt_blob}\n\n"
            f"For each primary sentence, output booleans indicating which alternates echo it.",
            max_tokens=600,
        )
        if parsed is None:
            return [0] * len(primary_sentences)
        raw_supports = parsed.get("supports") or []
        out: list[int] = []
        for i in range(len(primary_sentences)):
            if i < len(raw_supports) and isinstance(raw_supports[i], list):
                out.append(sum(1 for b in raw_supports[i] if bool(b)))
            else:
                out.append(0)
        return out


def run_audit(
    primary_content: str,
    alternate_contents: list[str],
    accepted_facts: list[tuple[str, str]],
    auditor: AuditorAgent | None = None,
) -> AuditReport:
    """Run corroboration + citation + consistency in a single pass.

    accepted_facts: list of (fact_text, source_url) tuples, in order.
    """
    sentences = split_sentences(primary_content)
    auditor = auditor or AuditorAgent()
    if auditor._groq is None:  # noqa: SLF001 — internal check for degraded mode
        return _empty_report(sentences, len(alternate_contents))

    facts = [
        FactClaim(idx=i + 1, text=text, source_url=url)
        for i, (text, url) in enumerate(accepted_facts)
    ]
    clusters, counts = auditor.corroborate(facts)
    corroborated = [c >= 2 for c in counts]
    citations, unsupported = auditor.audit_citations(sentences, facts)
    consistency = auditor.consistency_check(sentences, alternate_contents)

    issues: list[str] = []
    if unsupported:
        issues.append(f"{len(unsupported)} unsupported sentence(s) in synthesis")
    if sentences and consistency and min(consistency) == 0:
        issues.append("at least one sentence has zero consistency support")

    return AuditReport(
        clusters=clusters,
        corroboration_count=counts,
        corroborated_flags=corroborated,
        sentences=sentences,
        citations=citations,
        unsupported_sentence_indices=unsupported,
        alternate_contents=alternate_contents,
        consistency_support=consistency,
        issues=issues,
    )
